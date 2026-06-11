"""Gemeinsame HTTP-Helfer: GET mit Timeout, 1 Retry bei 5xx/Timeout (Backoff)."""

from __future__ import annotations

import asyncio

import httpx

from dashboard.logging_setup import get_logger

_log = get_logger("http")

_SERVER_ERROR_FLOOR = 500


def _backoff_seconds(attempt: int) -> float:
    """Exponentielles Backoff: 0.5s, 1.0s, 2.0s ..."""
    return 0.5 * float(2 ** (attempt - 1))


async def get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
    retries: int = 1,
) -> httpx.Response:
    """Fuehrt ein GET aus und wiederholt bei 5xx/Timeout/Transport-Fehlern.

    Raises:
        httpx.HTTPStatusError: bei 4xx oder nach erschoepften Retries (5xx).
        httpx.TransportError / httpx.TimeoutException: nach erschoepften Retries.
    """
    attempt = 0
    while True:
        try:
            response = await client.get(url, params=params, headers=headers, timeout=timeout)
            if response.status_code >= _SERVER_ERROR_FLOOR and attempt < retries:
                attempt += 1
                _log.warning("http_retry", url=url, status=response.status_code, attempt=attempt)
                await asyncio.sleep(_backoff_seconds(attempt))
                continue
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if attempt >= retries:
                raise
            attempt += 1
            _log.warning("http_retry", url=url, error=str(exc), attempt=attempt)
            await asyncio.sleep(_backoff_seconds(attempt))
