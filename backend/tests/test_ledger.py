from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest

from backend import ledger
from backend.importer import parse_workbook
from conftest import workbook_bytes


def preview(content=None):
    return ledger.add_proposal("import", parse_workbook(content or workbook_bytes(), "fixture.xlsx"))


def test_preview_has_no_postings_and_source_total_is_not_movement():
    p = preview()
    assert p["payload"]["stats"]["total"] == 2
    assert p["payload"]["errors"] == []
    assert ledger.metadata()["count"] == 0
    assert ledger.summary("2026-10")["income_minor"] == 0
    assert ledger.summary("2026-10")["net_position_minor"] is None


def test_confirm_reimport_and_concurrent_confirmation_are_idempotent():
    p = preview()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(ledger.confirm_proposal, [p["id"], p["id"]]))
    assert sum(r["inserted"] for r in results) == 2
    again = preview()
    assert again["payload"]["stats"]["duplicates"] == 2
    assert ledger.confirm_proposal(again["id"])["inserted"] == 0
    s = ledger.summary("2026-10", "efectivo")
    assert s["income_minor"] == 50000
    assert s["expense_minor"] == 12000
    assert s["accounts"][0]["balance_minor"] == 138000


def test_legitimate_identical_postings_survive_reimports():
    row = [1, date(2026, 10, 3), "Egreso", "Nómina y sueldos", "Dos pagos legítimos", None, None, None, 10.01]
    data = workbook_bytes([row, row])
    p = preview(data)
    ledger.confirm_proposal(p["id"])
    assert ledger.summary("2026-10")["expense_minor"] == 2002
    assert preview(data)["payload"]["stats"]["duplicates"] == 2


def test_card_charge_and_payment_affect_debt_not_operating_income():
    rows = [[1, date(2026, 10, 1), "Cargo", "Nómina y sueldos", "Cargo ficticio", None, None, 100.25, None],
            [2, date(2026, 10, 2), "Pago", "Pago de tarjeta", "Pago ficticio", None, None, None, 50]]
    p = preview(workbook_bytes(rows, "tarjeta_bbva", 1000))
    ledger.confirm_proposal(p["id"])
    s = ledger.summary("2026-10", "tarjeta_bbva")
    assert s["income_minor"] == 0
    assert s["expense_minor"] == 10025
    assert s["accounts"][0]["balance_minor"] == -105025
    assert s["excluded_count"] == 1


def test_invalid_rows_block_and_explicit_correction_stays_pending():
    rows = [[1, date(2026, 10, 1), "Ingreso", "Nómina y sueldos", "Tipo incorrecto", None, None, None, 50]]
    p = preview(workbook_bytes(rows))
    assert len(p["payload"]["errors"]) == 1
    with pytest.raises(ValueError):
        ledger.confirm_proposal(p["id"])
    data = {**p["payload"]["errors"][0]["draft"], "kind": "egreso", "amount_minor": 5000}
    fixed = ledger.correct_import(p["id"], "Movimientos Efectivo", 4, data, "Tipo verificado por el usuario")
    assert fixed["payload"]["errors"] == []
    assert len(fixed["payload"]["corrections"]) == 1
    assert ledger.metadata()["count"] == 0
    ledger.confirm_proposal(p["id"])
    assert ledger.query_movements()[0]["source_row"] == 4
    assert ledger.summary()["expense_minor"] == 5000


def test_failed_opening_change_rolls_back_entire_commit():
    ledger.confirm_proposal(preview()["id"])
    p = preview(workbook_bytes([[9, date(2026, 10, 9), "Ingreso", "Comisión de Renta", "Otro cobro", None, None, 100, None]], opening=999))
    with pytest.raises(ValueError):
        ledger.confirm_proposal(p["id"])
    assert ledger.metadata()["count"] == 2
    assert ledger.get_proposal(p["id"])["status"] == "pending"


def test_rejection_cannot_later_be_confirmed():
    p = preview()
    ledger.reject_proposal(p["id"])
    with pytest.raises(ValueError):
        ledger.confirm_proposal(p["id"])
    assert ledger.metadata()["count"] == 0


def test_period_and_reference_filters_are_exact():
    ledger.confirm_proposal(preview()["id"])
    assert len(ledger.query_movements("2026-10", search="DEMO-1")) == 1
    assert ledger.query_movements("2026-11") == []
    with pytest.raises(ValueError):
        ledger.query_movements("2026-13")
    assert ledger.query_movements(ids=[]) == []


@pytest.mark.parametrize("category,kind,expected", [
    ("Pago de tarjeta", "egreso", "card_payment"),
    ("Depósito en garantía recibido", "ingreso", "custody"),
    ("Aportación de socios", "ingreso", "financing"),
    ("Préstamos otorgados", "egreso", "financing"),
    ("Traspaso entre cuentas", "egreso", "transfer"),
    ("Por revisar", "ingreso", "por_revisar"),
])
def test_nonoperating_movements_are_not_revenue_or_expense(category, kind, expected):
    assert ledger.treatment(category, kind) == expected
    assert ledger.totals([{"amount_minor": 10000, "treatment": expected, "kind": kind}])["income_minor"] == 0


def test_refunds_reduce_expenses_and_do_not_inflate_revenue():
    rows = [{"amount_minor": -10025, "kind": "cargo", "treatment": "operational"},
            {"amount_minor": 2025, "kind": "devolucion", "treatment": "operational"}]
    assert ledger.totals(rows)["income_minor"] == 0
    assert ledger.totals(rows)["expense_minor"] == 8000


def test_money_stays_exact_in_cents():
    assert ledger.money("0.10") + ledger.money("0.20") == 30
    assert ledger.money(74284.10999999999) == 7428411
    with pytest.raises(ValueError):
        ledger.money("NaN")
