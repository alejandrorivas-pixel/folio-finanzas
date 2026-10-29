"""Synthetic OOXML test inputs only; never copy a real financial workbook here."""
import io
from datetime import date
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from backend import ledger
from backend.main import app

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def workbook_bytes(rows=None, account="efectivo", opening=1000, footer=True):
    rows = rows if rows is not None else [
        [1, date(2026, 10, 1), "Ingreso", "Comisión de Renta", "Comisión ficticia", None, "DEMO-1", 500, None],
        [2, date(2026, 10, 2), "Egreso", "Nómina y sueldos", "Nómina ficticia", None, None, None, 120],
    ]
    names = {"efectivo": ("Movimientos Efectivo", "Balance Efectivo", "C5"),
             "banco": ("Movimientos Banco", "Balance Banco", "C5"),
             "tarjeta_bbva": ("Movimientos Tarjeta BBVA", "Balance Tarjeta BBVA", "C9")}
    name, balance, initial = names[account]
    sheets = {
        name: [("A3", "#"), ("B3", "Fecha"), ("C3", "Tipo"), ("D3", "Categoría"), ("E3", "Concepto / Descripción")],
        balance: [(initial, opening)],
        "Catalogos": [("A2", "Comisión de Renta"), ("C2", "Nómina y sueldos"), ("C3", "Pago de tarjeta")],
    }
    for idx, row in enumerate(rows, 4):
        for col, value in enumerate(row):
            if value is not None:
                sheets[name].append((f"{chr(65 + col)}{idx}", value))
    if footer:
        n = len(rows) + 5
        sheets[name] += [(f"D{n}", "TOTAL"), (f"H{n}", 500), (f"I{n}", 120)]
    wb = Element("workbook", {"xmlns": NS, "xmlns:r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"})
    sheet_nodes = SubElement(wb, "sheets")
    rel = Element("Relationships", {"xmlns": "http://schemas.openxmlformats.org/package/2006/relationships"})
    content = Element("Types", {"xmlns": "http://schemas.openxmlformats.org/package/2006/content-types"})
    SubElement(content, "Default", Extension="rels", ContentType="application/vnd.openxmlformats-package.relationships+xml")
    SubElement(content, "Default", Extension="xml", ContentType="application/xml")
    SubElement(content, "Override", PartName="/xl/workbook.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")
    out = io.BytesIO()
    with ZipFile(out, "w") as z:
        for i, (title, cells) in enumerate(sheets.items(), 1):
            SubElement(sheet_nodes, "sheet", name=title, sheetId=str(i), attrib={"r:id": f"rId{i}"})
            SubElement(rel, "Relationship", Id=f"rId{i}", Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet", Target=f"worksheets/sheet{i}.xml")
            SubElement(content, "Override", PartName=f"/xl/worksheets/sheet{i}.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
            sheet = Element("worksheet", xmlns=NS)
            max_row = max(int(''.join(filter(str.isdigit, ref))) for ref, _ in cells)
            SubElement(sheet, "dimension", ref=f"A1:Q{max_row}")
            data = SubElement(sheet, "sheetData")
            by_row = {}
            for ref, value in cells:
                row_number = int(''.join(filter(str.isdigit, ref)))
                by_row.setdefault(row_number, []).append((ref, value))
            for n, values in sorted(by_row.items()):
                row = SubElement(data, "row", r=str(n))
                for ref, value in values:
                    if isinstance(value, date):
                        cell = SubElement(row, "c", r=ref, t="d")
                        SubElement(cell, "v").text = value.isoformat()
                    elif isinstance(value, (int, float)):
                        cell = SubElement(row, "c", r=ref, t="n")
                        SubElement(cell, "v").text = str(value)
                    else:
                        cell = SubElement(row, "c", r=ref, t="inlineStr")
                        SubElement(SubElement(cell, "is"), "t").text = str(value)
            z.writestr(f"xl/worksheets/sheet{i}.xml", tostring(sheet))
        z.writestr("xl/workbook.xml", tostring(wb))
        z.writestr("xl/_rels/workbook.xml.rels", tostring(rel))
        z.writestr("[Content_Types].xml", tostring(content))
        z.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    return out.getvalue()


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("FOLIO_DEMO", "0")
    monkeypatch.setenv("FINANZAS_DB", str(tmp_path / "test.sqlite"))
    ledger.init_db()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
