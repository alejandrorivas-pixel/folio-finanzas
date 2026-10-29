"""Bounded audio-to-text only. Transcription cannot create ledger entries."""
import os
import re
from pathlib import PurePosixPath

from openai import AsyncOpenAI

from . import ledger

MAX_AUDIO_BYTES = 10 * 1024 * 1024


def validate_audio(content: bytes, filename: str) -> tuple[str, str]:
    if not content or len(content) > MAX_AUDIO_BYTES:
        raise ValueError("El audio debe contener datos y pesar como máximo 10 MB")
    name = PurePosixPath(filename.replace("\\", "/")).name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)[:180]
    extension = PurePosixPath(name).suffix.lower()
    formats = {
        ".wav": ("audio/wav", content[:4] == b"RIFF" and content[8:12] == b"WAVE"),
        ".webm": ("audio/webm", content[:4] == b"\x1a\x45\xdf\xa3"),
        ".mp3": ("audio/mpeg", content[:3] == b"ID3" or (len(content) > 2 and content[0] == 255 and content[1] & 224 == 224)),
        ".mp4": ("audio/mp4", content[4:8] == b"ftyp"),
        ".m4a": ("audio/mp4", content[4:8] == b"ftyp"),
    }
    if extension not in formats:
        raise ValueError("Usa un audio MP3, MP4, M4A, WAV o WebM")
    mime, matches = formats[extension]
    if not matches or len(content) < 16:
        raise ValueError("El contenido del audio no corresponde a su formato")
    return name, mime


async def transcribe(content: bytes, filename: str) -> dict:
    if ledger.demo_mode():
        raise ValueError("La demostración solo utiliza el dictado ficticio de ejemplo; no envía grabaciones")
    name, mime = validate_audio(content, filename)
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise ValueError("Arranca el servidor desde la terminal donde configuraste la clave de OpenAI para transcribir")
    model = os.environ.get("OPENAI_TRANSCRIBE_MODEL", "gpt-transcribe")
    hints = {"languages": ["es"]} if model == "gpt-transcribe" else {"language": "es"}
    # Pass bytes directly; no audio files or provider File objects are retained.
    async with AsyncOpenAI(timeout=60.0, max_retries=0) as client:
        result = await client.audio.transcriptions.create(
            model=model, file=(name, content, mime), **hints,
        )
    text = getattr(result, "text", "").strip()
    if not text:
        raise ValueError("No se reconoció voz. Vuelve a grabar cerca del micrófono o escribe el movimiento")
    if len(text) > 3000:
        raise ValueError("La transcripción excede 3,000 caracteres. Divide el dictado en movimientos más cortos")
    return {"text": text, "model": model, "language": "es"}
