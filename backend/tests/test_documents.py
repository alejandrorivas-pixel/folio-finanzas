"""Document intake uses newly generated fictional files and a mocked provider."""
import asyncio
import base64
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from pypdf import PdfWriter

from backend import documents, ledger


def image_bytes(format="PNG", size=(32, 24)):
    output = io.BytesIO()
    Image.new("RGB", size, "white").save(output, format=format)
    return output.getvalue()


def pdf_bytes(pages=1, encrypted=False):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    if encrypted:
        writer.encrypt("fake-test-password")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def extracted_row(**overrides):
    return {
        "page": 1, "date": "2026-10-12", "kind": "egreso", "description": "Proveedor ficticio de demostración",
        "amount_pesos": "123.45", "currency": "MXN", "currency_evidence": "Importe en MXN",
        "category": "Pago a proveedores", "reference": "REF-DEMO-001", "property": None,
        "is_completed": True, "uncertain_fields": [], "warnings": [], **overrides,
    }


def mock_extraction(monkeypatch, rows=None, warnings=None, status="completed", parsed=True):
    monkeypatch.setenv("OPENAI_API_KEY", "test-dummy-not-a-real-key")
    extraction = documents.DocumentExtraction.model_validate({
        "movements": rows if rows is not None else [extracted_row()], "warnings": warnings or [],
    })
    parse = AsyncMock(return_value=SimpleNamespace(status=status, output_parsed=extraction if parsed else None))
    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return client

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(documents, "AsyncOpenAI", FakeClient)
    return parse


def extract(content=None, filename="captura-demo.png", account="banco"):
    return asyncio.run(documents.extract_document(content or image_bytes(), filename, account))


def test_document_proposal_requires_confirmation_and_reimport_is_duplicate(monkeypatch):
    parse = mock_extraction(monkeypatch, [extracted_row(), extracted_row(amount_pesos="0.55", reference="REF-DEMO-002")])
    payload = extract()
    assert payload["stats"]["expense_minor"] == 12400
    assert payload["stats"]["new"] == 2
    assert payload["movements"][0]["source_row"] == 4
    assert payload["movements"][0]["source_sheet"] == "Página 1"
    assert payload["movements"][0]["source_file"] == "captura-demo.png"
    assert len(payload["file_hash"]) == 64
    assert ledger.metadata()["count"] == 0
    assert ledger.metadata()["pending"] == 0
    proposal = ledger.add_proposal("import", payload)
    assert ledger.metadata()["count"] == 0
    assert ledger.confirm_proposal(proposal["id"])["inserted"] == 2
    repeat = extract()
    assert repeat["stats"]["duplicates"] == 2
    assert repeat["stats"]["new"] == 0
    request = parse.call_args.kwargs
    assert request["store"] is False
    assert request["text_format"] is documents.DocumentExtraction
    attachment = request["input"][0]["content"][1]
    assert attachment["type"] == "input_image"
    assert base64.b64decode(attachment["image_url"].split(",", 1)[1]) == image_bytes()
    assert "file_id" not in attachment and "file_url" not in attachment
    assert "file_data" not in str(payload)


def test_pdf_inline_request_and_page_provenance(monkeypatch):
    parse = mock_extraction(monkeypatch, [extracted_row(page=2)])
    content = pdf_bytes(pages=2)
    payload = extract(content, "../estado-demo.pdf")
    assert payload["filename"] == "estado-demo.pdf"
    assert payload["document"]["pages"] == 2
    assert payload["movements"][0]["source_sheet"] == "Página 2"
    attachment = parse.call_args.kwargs["input"][0]["content"][1]
    assert attachment["type"] == "input_file"
    assert attachment["filename"] == "estado-demo.pdf"
    assert base64.b64decode(attachment["file_data"].split(",", 1)[1]) == content
    assert "file_id" not in attachment and "file_url" not in attachment


@pytest.mark.parametrize("change", [
    {"amount_pesos": "123.456"}, {"amount_pesos": "1,234.50"}, {"amount_pesos": "1e3"},
    {"amount_pesos": "NaN"}, {"amount_pesos": None}, {"amount_pesos": "0"},
    {"currency": None, "currency_evidence": "$"}, {"currency_evidence": "$"},
    {"date": None}, {"date": "2026-02-30"}, {"date": "20261012"},
    {"kind": None}, {"description": None}, {"is_completed": None},
    {"page": 2}, {"uncertain_fields": ["amount_pesos"]}, {"warnings": ["Fecha poco legible"]},
])
def test_uncertain_fields_block_confirmation_without_rounding_or_guessing(monkeypatch, change):
    mock_extraction(monkeypatch, [extracted_row(**change)])
    payload = extract()
    assert not payload["movements"]
    assert payload["stats"]["errors"] == 1
    assert payload["errors"][0]["draft"]["account"] == "banco"
    if "amount_pesos" in change:
        assert payload["errors"][0]["draft"]["amount_minor"] is None
    proposal = ledger.add_proposal("import", payload)
    with pytest.raises(ValueError, match="errores"):
        ledger.confirm_proposal(proposal["id"])
    assert ledger.metadata()["count"] == 0


def test_explicit_foreign_currency_is_rejected_without_proposal(monkeypatch):
    mock_extraction(monkeypatch, [extracted_row(currency="USD", currency_evidence="USD")])
    with pytest.raises(ValueError, match="distinta de MXN"):
        extract()
    assert ledger.metadata()["pending"] == 0
    assert ledger.metadata()["count"] == 0


def test_manual_correction_is_audited_and_stays_pending(monkeypatch):
    mock_extraction(monkeypatch, [extracted_row(amount_pesos=None, uncertain_fields=["amount_pesos"])])
    proposal = ledger.add_proposal("import", extract())
    error = proposal["payload"]["errors"][0]
    corrected = ledger.correct_import(proposal["id"], error["sheet"], error["row"],
                                     {**error["draft"], "amount_minor": 12345}, "Revisé el comprobante ficticio")
    assert corrected["status"] == "pending"
    assert corrected["payload"]["stats"]["errors"] == 0
    assert corrected["payload"]["movements"][0]["amount_minor"] == -12345
    assert corrected["payload"]["corrections"][0]["before"]["extraction"]["amount_pesos"] is None
    assert ledger.metadata()["count"] == 0


def test_partial_extraction_warning_blocks_every_row(monkeypatch):
    mock_extraction(monkeypatch, warnings=["La página está cortada; puede haber movimientos fuera de la imagen"])
    payload = extract()
    assert payload["stats"]["errors"] == 1
    assert payload["document"]["requires_review"] is True
    assert not payload["movements"]


@pytest.mark.parametrize("rows,status,parsed,match", [
    ([], "completed", True, "No se encontraron"),
    ([extracted_row()], "incomplete", True, "completar"),
    ([extracted_row()], "completed", False, "completar"),
])
def test_empty_or_incomplete_provider_output_never_posts(monkeypatch, rows, status, parsed, match):
    mock_extraction(monkeypatch, rows, status=status, parsed=parsed)
    with pytest.raises(ValueError, match=match):
        extract()
    assert ledger.metadata()["count"] == 0
    assert ledger.metadata()["pending"] == 0


@pytest.mark.parametrize("content,filename,match", [
    (b"text", "fake.pdf", "PDF válido"), (b"%PDF-1.7\ninvalid", "broken.pdf", "leer el PDF"),
    (b"text", "fake.png", "extensión"), (b"text", "unsupported.svg", "PNG, JPEG"),
    (b"\x89PNG\r\n\x1a\ninvalid", "broken.png", "dañada"),
    (b"a" * (documents.MAX_BYTES + 1), "big.pdf", "10 MB"),
])
def test_invalid_files_rejected_before_provider(monkeypatch, content, filename, match):
    parse = mock_extraction(monkeypatch)
    with pytest.raises(ValueError, match=match):
        extract(content, filename)
    parse.assert_not_awaited()


def test_pdf_page_and_encryption_limits():
    with pytest.raises(ValueError, match="10 páginas"):
        documents.validate_document(pdf_bytes(11), "long-demo.pdf")
    with pytest.raises(ValueError, match="cifrado"):
        documents.validate_document(pdf_bytes(encrypted=True), "encrypted-demo.pdf")
    with pytest.raises(ValueError, match="10 páginas"):
        documents.validate_document(pdf_bytes(0), "empty-demo.pdf")


def test_image_pixel_limit(monkeypatch):
    monkeypatch.setattr(documents, "MAX_PIXELS", 100)
    with pytest.raises(ValueError, match="megapíxeles"):
        documents.validate_document(image_bytes(size=(11, 10)), "large-demo.png")


@pytest.mark.parametrize("format,filename", [("PNG", "demo.png"), ("JPEG", "demo.jpeg"), ("WEBP", "demo.webp")])
def test_supported_static_image_types(format, filename):
    info = documents.validate_document(image_bytes(format), filename)
    assert info["pages"] == 1


def test_account_and_demo_guards_precede_provider(monkeypatch):
    parse = mock_extraction(monkeypatch)
    with pytest.raises(ValueError, match="cuenta"):
        extract(account="invented")
    monkeypatch.setenv("FOLIO_DEMO", "1")
    with pytest.raises(ValueError, match="ficticios"):
        extract()
    parse.assert_not_awaited()


def test_missing_key_is_explicit_without_provider_call(monkeypatch):
    parse = mock_extraction(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="clave"):
        extract()
    parse.assert_not_awaited()
