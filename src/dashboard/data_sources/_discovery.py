"""Hilfsfunktion: aktuellen Datei-Link auf einer HTML-Seite finden (Link-Discovery).

Shiller- und NAAIM-Dateien tragen datierte/versionierte Dateinamen, die sich
periodisch aendern. Statt einer statischen URL ermitteln wir den aktuellen Link
direkt von der Quellseite (es wird ein Link gesucht, keine Daten gescraped).
"""

from __future__ import annotations

import re

import httpx

from dashboard.config import Settings
from dashboard.data_sources._http import get_with_retry


async def discover_file_url(
    client: httpx.AsyncClient,
    page_url: str,
    pattern: str,
    settings: Settings,
) -> str | None:
    """Sucht den ersten zu ``pattern`` passenden Datei-Link auf ``page_url``.

    Returns:
        Absolute URL oder None, wenn nichts gefunden/Seite nicht erreichbar.
    """
    headers = {"User-Agent": settings.user_agent}
    try:
        response = await get_with_retry(
            client,
            page_url,
            headers=headers,
            timeout=settings.http_timeout_seconds,
            retries=settings.http_retries,
        )
    except httpx.HTTPError:
        return None

    match = re.search(pattern, response.text, re.IGNORECASE)
    if match is None:
        return None
    url = match.group(0)
    if url.startswith("//"):
        url = "https:" + url
    return url
