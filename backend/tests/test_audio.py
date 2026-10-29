import asyncio
import io
import wave
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend import audio, ai, ledger


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(8000)
        recording.writeframes(b"\0\0" * 800)
    return output.getvalue()


def mock_transcription(monkeypatch, text="Hoy pagué 350 pesos en efectivo a Proveedor Demo"):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-real-key")
    create = AsyncMock(return_value=SimpleNamespace(text=text))

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create)))

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(audio, "AsyncOpenAI", FakeClient)
    return create


def test_transcription_is_editable_text_and_never_a_proposal(client, monkeypatch):
    create = mock_transcription(monkeypatch)
    response = client.post("/api/audio/transcribe", files={"file": ("../dictado-demo.wav", wav_bytes(), "audio/wav")})
    assert response.status_code == 200
    assert response.json() == {"text": "Hoy pagué 350 pesos en efectivo a Proveedor Demo", "model": "gpt-transcribe", "language": "es"}
    assert ledger.metadata()["pending"] == ledger.metadata()["count"] == 0
    arguments = create.call_args.kwargs
    assert arguments["file"][0] == "dictado-demo.wav"
    assert arguments["languages"] == ["es"]


def test_explicit_whisper_override_uses_legacy_language_hint(monkeypatch):
    create = mock_transcription(monkeypatch)
    monkeypatch.setenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1")
    response = asyncio.run(audio.transcribe(wav_bytes(), "dictado-demo.wav"))
    assert response["model"] == "whisper-1"
    assert create.call_args.kwargs["language"] == "es"
    assert "languages" not in create.call_args.kwargs


@pytest.mark.parametrize("name,content", [
    ("vacio.wav", b""), ("falso.wav", b"not audio" * 20),
    ("archivo.txt", b"not audio" * 20), ("mal.mp4", wav_bytes()),
    ("enorme.wav", b"0" * (audio.MAX_AUDIO_BYTES + 1)),
])
def test_invalid_audio_rejected_before_provider(client, monkeypatch, name, content):
    create = mock_transcription(monkeypatch)
    response = client.post("/api/audio/transcribe", files={"file": (name, content)})
    assert response.status_code == 400
    create.assert_not_awaited()
    assert ledger.metadata()["pending"] == 0


def test_demo_cannot_transmit_recordings(client, monkeypatch):
    monkeypatch.setenv("FOLIO_DEMO", "1")
    create = mock_transcription(monkeypatch)
    response = client.post("/api/audio/transcribe", files={"file": ("dictado-demo.wav", wav_bytes())})
    assert response.status_code == 400
    assert "ficticio" in response.json()["detail"]
    create.assert_not_awaited()


@pytest.mark.parametrize("text", ["", "   ", "x" * 3001])
def test_empty_or_oversize_transcript_is_an_error_not_a_record(client, monkeypatch, text):
    mock_transcription(monkeypatch, text)
    response = client.post("/api/audio/transcribe", files={"file": ("dictado-demo.wav", wav_bytes())})
    assert response.status_code == 400
    assert ledger.metadata()["count"] == ledger.metadata()["pending"] == 0


def test_provider_details_do_not_leak(client, monkeypatch):
    create = mock_transcription(monkeypatch)
    create.side_effect = RuntimeError("private-provider-payload-must-not-be-returned")
    response = client.post("/api/audio/transcribe", files={"file": ("dictado-demo.wav", wav_bytes())})
    assert response.status_code == 502
    assert "private-provider" not in response.text
    assert ledger.metadata()["count"] == 0


def test_key_is_required_without_exposing_it(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.post("/api/audio/transcribe", files={"file": ("dictado-demo.wav", wav_bytes())})
    assert response.status_code == 400
    assert "clave" in response.json()["detail"]


@pytest.mark.parametrize("currency,amount", [("USD", "100"), (None, "100"), ("MXN", "100.999"), ("MXN", "1e3")])
def test_capture_does_not_assume_currency_or_round_uncertain_spoken_amounts(monkeypatch, currency, amount):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-real-key")
    draft = ai.CaptureDraft(date="2026-10-28", account="efectivo", kind="egreso",
        category="Pago a proveedores", description="Proveedor Demo ficticio", amount_pesos=amount,
        reference=None, property=None, question=None, currency=currency)
    monkeypatch.setattr(ai.Runner, "run", AsyncMock(return_value=SimpleNamespace(final_output=draft)))
    result = asyncio.run(ai.capture("Dictado de prueba"))
    assert result["proposal"] is None
    assert ledger.metadata()["pending"] == ledger.metadata()["count"] == 0


@pytest.mark.parametrize("value", [False, 1, "true", "yes"])
def test_confirm_requires_json_boolean_true(client, value):
    proposal = ledger.add_proposal("manual", {"movements": [], "errors": []})
    response = client.post(f"/api/proposals/{proposal['id']}/confirm", json={"confirm": value})
    assert response.status_code == 422
    assert ledger.get_proposal(proposal["id"])["status"] == "pending"
