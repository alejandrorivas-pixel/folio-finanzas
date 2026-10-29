from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
import io
import os
import hashlib
import json
import copy
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictInt, StrictBool, field_validator

from . import ledger
from .importer import parse_workbook

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env.local", override=False)


@asynccontextmanager
async def lifespan(app):
    ledger.init_db()
    if ledger.demo_mode():
        from .demo_data import seed
        seed()
    yield


app = FastAPI(title="Folio · Finanzas de tu negocio", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


class Confirmation(BaseModel):
    confirm: StrictBool

    @field_validator("confirm")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("Se requiere confirmación explícita")
        return value


class Manual(BaseModel):
    date: str
    account: str
    kind: str
    category: str
    description: str = Field(min_length=1, max_length=1000)
    amount_minor: StrictInt
    reference: str | None = Field(default=None, max_length=300)
    property: str | None = Field(default=None, max_length=100)


class AgentManual(Manual):
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]+$")


class Chat(BaseModel):
    message: str = Field(min_length=1, max_length=3000)
    mode: Literal["analyst", "capture"] = "analyst"
    month: str | None = None
    account: str | None = None
    history: list[dict[str, str]] = Field(default_factory=list, max_length=10)


class ImportCorrection(BaseModel):
    sheet: str = Field(max_length=100)
    row: int = Field(gt=3)
    movement: Manual
    reason: str = Field(min_length=1, max_length=1000)


class DocumentDemo(BaseModel):
    format: Literal["pdf", "image"]
    account: Literal["efectivo", "banco", "tarjeta_bbva"]


async def provider_result(operation, timeout=75):
    """Expose useful errors without provider payloads, keys or uploaded content."""
    try:
        return await asyncio.wait_for(operation, timeout=timeout)
    except ValueError:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(504, "La lectura tardó demasiado. Prueba con un archivo o dictado más corto.")
    except Exception as exc:
        code = getattr(exc, "status_code", None)
        if code in (401, 403):
            raise HTTPException(502, "OpenAI rechazó la conexión. Revisa la clave y los permisos del proyecto.")
        if code == 429:
            raise HTTPException(429, "OpenAI indicó un límite de uso o saldo insuficiente. Revisa tu proyecto antes de reintentar.")
        raise HTTPException(502, "No se pudo completar la lectura con IA. Revisa el formato e intenta de nuevo; no se guardó ningún movimiento.")


@app.exception_handler(ValueError)
async def value_error(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(KeyError)
async def key_error(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=404, content={"detail": str(exc.args[0])})


@app.get("/health")
def health():
    return {"application": "folio", "status": "ok", "ai_configured": bool(os.environ.get("OPENAI_API_KEY", "").strip()), "model": os.environ.get("OPENAI_MODEL", "gpt-5.4-mini"), "demo_mode": ledger.demo_mode()}


@app.get("/api/meta")
def meta():
    return {**ledger.metadata(), "local_workbook_available": ledger.demo_mode(), "demo_mode": ledger.demo_mode(), "company_name": "Empresa Demo" if ledger.demo_mode() else "Mi empresa"}


@app.get("/api/summary")
def summary(month: str | None = None, account: str | None = None):
    return ledger.summary(month or None, account or None)


@app.get("/api/movements")
def movements(month: str | None = None, account: str | None = None, category: str | None = None,
              search: str | None = None, ids: str | None = None, page: int = 1, size: int = 25):
    if page < 1 or size < 1 or size > 100:
        raise ValueError("Paginación inválida")
    rows = ledger.query_movements(month or None, account or None, category or None, search or None,
        ids.split(",") if ids is not None else None)
    return {"items": rows[(page - 1) * size:page * size], "total": len(rows), "page": page, "size": size, "totals": ledger.totals(rows)}


@app.get("/api/movements/{mid}")
def movement(mid: str):
    rows = ledger.query_movements(ids=[mid])
    if not rows:
        raise KeyError("Movimiento no encontrado")
    return rows[0]


@app.post("/api/imports/preview")
async def preview(file: UploadFile = File(...)):
    if ledger.demo_mode():
        raise ValueError("La demostración solo utiliza datos ficticios. Usa Cargar ejemplo ficticio; no subas documentos reales.")
    if not str(file.filename).lower().endswith(".xlsx"):
        raise ValueError("Selecciona un archivo .xlsx")
    content = await file.read(15 * 1024 * 1024 + 1)
    payload = await asyncio.to_thread(parse_workbook, content, Path(file.filename).name)
    return ledger.add_proposal("import", payload)


@app.post("/api/imports/local-preview")
def local_preview():
    if not ledger.demo_mode():
        raise KeyError("Selecciona explícitamente el archivo XLSX que quieras importar")
    from .demo_data import payload
    return ledger.add_proposal("import", payload())


# Serialize document extraction so a double click cannot create differently
# interpreted copies of the same file. This local app runs one worker.
document_lock = asyncio.Lock()


@app.post("/api/imports/document-preview")
async def document_preview(file: UploadFile = File(...), account: str = Form(...)):
    from .documents import MAX_BYTES, extract_document, validate_document
    from .importer import refresh_preview
    try:
        if ledger.demo_mode():
            raise ValueError("La demostración solo utiliza documentos ficticios. Usa los ejemplos PDF o captura.")
        if account not in {a["id"] for a in ledger.ACCOUNTS}:
            raise ValueError("Selecciona la cuenta a la que pertenece el documento")
        content = await file.read(MAX_BYTES + 1)
        document = await asyncio.to_thread(validate_document, content, file.filename or "")
        digest = hashlib.sha256(content).hexdigest()
        async with document_lock:
            # Reuse the reviewed extraction for identical bytes/account, including
            # confirmed imports, rather than asking the model to interpret again.
            with ledger.connection() as con:
                cached = con.execute("SELECT id,status,payload FROM proposals WHERE kind='import' AND status!='rejected' ORDER BY created_at DESC").fetchall()
            for row in cached:
                payload = json.loads(row["payload"])
                if payload.get("document", {}).get("account") == account and payload.get("file_hash") == digest:
                    if row["status"] == "pending":
                        return ledger.get_proposal(row["id"])
                    payload = refresh_preview(copy.deepcopy(payload))
                    return ledger.add_proposal("import", payload)
            payload = await provider_result(extract_document(content, document["filename"], account))
            return ledger.add_proposal("import", payload)
    finally:
        await file.close()


@app.post("/api/imports/document-demo")
def document_demo(body: DocumentDemo):
    if not ledger.demo_mode():
        raise ValueError("Los ejemplos ficticios solo están disponibles en modo demo")
    from .demo_data import document_payload
    return ledger.add_proposal("import", document_payload(body.format, body.account))


@app.post("/api/audio/transcribe")
async def audio_transcribe(file: UploadFile = File(...)):
    from .audio import MAX_AUDIO_BYTES, transcribe
    try:
        if ledger.demo_mode():
            raise ValueError("La demostración solo utiliza el dictado ficticio de ejemplo; no envía grabaciones")
        content = await file.read(MAX_AUDIO_BYTES + 1)
        return await provider_result(transcribe(content, file.filename or ""))
    finally:
        await file.close()


@app.get("/api/proposals")
def proposals():
    return ledger.pending_proposals()


@app.post("/api/proposals/manual")
def manual(body: Manual):
    r = ledger.validate_manual(body.model_dump())
    return ledger.add_proposal("manual", {"movements": [r], "errors": [], "notes": [], "openings": [], "categories": []})


@app.post("/api/agent/proposals/manual")
def agent_manual(body: AgentManual):
    try:
        return ledger.propose_agent_movement(body.request_id, body.model_dump(exclude={"request_id"}))
    except ledger.IdempotencyConflict as exc:
        raise HTTPException(409, str(exc))


@app.get("/api/proposals/{pid}")
def proposal(pid: str):
    return ledger.get_proposal(pid)


@app.post("/api/proposals/{pid}/confirm")
def confirm(pid: str, body: Confirmation):
    return ledger.confirm_proposal(pid)


@app.post("/api/proposals/{pid}/corrections")
def correct_import(pid: str, body: ImportCorrection):
    return ledger.correct_import(pid, body.sheet, body.row, body.movement.model_dump(), body.reason)


@app.post("/api/proposals/{pid}/reject")
def reject(pid: str, body: Confirmation):
    ledger.reject_proposal(pid)
    return {"status": "rejected"}


@app.post("/api/chat")
async def chat(body: Chat):
    from . import ai
    ai.check_key()
    ledger.bounds(body.month)
    try:
        if body.mode == "capture":
            return await asyncio.wait_for(ai.capture(body.message, body.history), timeout=60)
        return await asyncio.wait_for(ai.analyze(body.message, body.month, body.account, body.history), timeout=60)
    except ValueError:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(504, "El agente tardó demasiado. Intenta una consulta más concreta.")
    except Exception as exc:
        code = getattr(exc, "status_code", None)
        if code in (401, 403):
            raise HTTPException(502, "OpenAI rechazó la conexión. Revisa la clave y los permisos del proyecto.")
        if code == 429:
            raise HTTPException(429, "OpenAI indicó un límite de uso o saldo insuficiente. Revisa tu proyecto antes de reintentar.")
        raise HTTPException(502, "No se pudo completar la consulta de IA. Los movimientos confirmados siguen disponibles.")


@app.get("/api/export")
def export(month: str | None = None, account: str | None = None):
    import csv
    rows = ledger.query_movements(month or None, account or None)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["id", "fecha", "cuenta", "tipo", "categoria", "descripcion", "importe_MXN", "referencia", "propiedad", "tratamiento", "archivo", "hoja", "fila"])
    def safe(value):
        if value is None:
            return ""
        s = str(value)
        return "'" + s if s.startswith(("=", "+", "-", "@", "\t", "\r")) else s
    for r in rows:
        amount = str(ledger.Decimal(r["amount_minor"]) / 100)
        writer.writerow([safe(r[k]) for k in ["id", "date", "account", "kind", "category", "description"]] + [amount] +
            [safe(r.get(k)) for k in ["reference", "property", "treatment", "source_file", "source_sheet", "source_row"]])
    return StreamingResponse(iter(["\ufeff" + out.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="folio-movimientos.csv"'})


DIST = ROOT / "frontend" / "dist"
if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        file = DIST / path
        if file.is_file() and file.resolve().is_relative_to(DIST.resolve()):
            return FileResponse(file)
        return FileResponse(DIST / "index.html")
