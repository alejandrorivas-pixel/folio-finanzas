"""Small, constrained HTTP bridge to the running local Folio application."""
from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlsplit

import httpx


class FolioClientError(Exception):
    """An actionable error that is safe to return to an agent."""


def validate_api_url(value: str) -> str:
    """Accept only an explicit, unprivileged loopback HTTP port."""
    try:
        parsed = urlsplit(value)
        valid = (
            value == value.strip()
            and parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost"}
            and parsed.username is None
            and parsed.password is None
            and parsed.path in {"", "/"}
            and "?" not in value
            and "#" not in value
            and parsed.port is not None
            and 1024 <= parsed.port <= 65535
            and parsed.netloc == f"{parsed.hostname}:{parsed.port}"
        )
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise FolioClientError(
            "FOLIO_API_URL debe ser http://127.0.0.1:PUERTO o "
            "http://localhost:PUERTO, con puerto entre 1024 y 65535."
        )
    return f"http://{parsed.hostname}:{parsed.port}"


_GET_ROUTES = {
    "/health", "/api/meta", "/api/summary", "/api/movements", "/api/proposals",
}
_GET_ITEM = re.compile(r"/api/(?:movements|proposals)/[A-Za-z0-9_-]{1,100}\Z")


class FolioClient:
    """No generic agent HTTP tool, redirects, proxy environment, or DB access."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = validate_api_url(
            base_url if base_url is not None
            else os.environ.get("FOLIO_API_URL", "http://127.0.0.1:8000")
        )
        self.transport = transport

    @staticmethod
    def _decode(response: httpx.Response) -> Any:
        if response.is_redirect:
            raise FolioClientError("Folio devolvió una redirección; revisa el puerto local.")
        messages = {
            400: "Folio rechazó los datos. Revisa fecha, cuenta, categoría, tipo e importe.",
            401: "La instancia de Folio requiere autorización.",
            403: "La instancia de Folio rechazó el acceso.",
            404: "No se encontró el movimiento, propuesta o endpoint de Folio.",
            409: "Ese request_id ya se usó con otros datos. Reutilízalo solo para reintentar la misma propuesta.",
            422: "Datos inválidos. Consulta folio_catalog y envía importes positivos en centavos enteros.",
            429: "Folio indicó un límite de solicitudes. Intenta más tarde.",
        }
        if response.status_code >= 400:
            raise FolioClientError(messages.get(
                response.status_code,
                "Folio no pudo completar la operación. Revisa la aplicación local.",
            ))
        if not 200 <= response.status_code < 300:
            raise FolioClientError("Respuesta inesperada de la aplicación local.")
        try:
            return response.json()
        except (ValueError, UnicodeError):
            raise FolioClientError("El puerto local no devolvió una respuesta JSON válida de Folio.") from None

    async def _request(
        self, method: str, path: str, *, params: dict | None = None,
        payload: dict | None = None,
    ) -> Any:
        allowed = (
            method == "GET" and (path in _GET_ROUTES or _GET_ITEM.fullmatch(path))
        ) or (method == "POST" and path == "/api/agent/proposals/manual")
        if not allowed:
            raise FolioClientError("Esta operación no está disponible para agentes.")
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(30.0, connect=3.0),
                follow_redirects=False,
                trust_env=False,
                transport=self.transport,
                headers={"Accept": "application/json"},
            ) as client:
                identity = self._decode(await client.get("/health"))
                if not isinstance(identity, dict) or identity.get("application") != "folio":
                    raise FolioClientError(
                        "El puerto no corresponde a Folio o usa una versión anterior. "
                        "Inicia la versión actual con ./start.sh."
                    )
                if path == "/health":
                    return identity
                return self._decode(await client.request(
                    method, path, params=params, json=payload,
                ))
        except httpx.TimeoutException:
            raise FolioClientError("Folio tardó demasiado en responder. Revisa la aplicación local.") from None
        except httpx.HTTPError:
            raise FolioClientError(
                "No se pudo conectar con Folio. Inicia ./start.sh y verifica FOLIO_API_URL."
            ) from None

    async def status(self) -> dict:
        return await self.get("/health")

    async def get(self, path: str, params: dict | None = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, payload: dict) -> Any:
        return await self._request("POST", path, payload=payload)
