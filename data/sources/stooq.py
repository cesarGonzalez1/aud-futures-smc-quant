"""Adaptador Stooq — fuente secundaria SOLO para DXY diario (ADR-005).

Stooq expone descarga directa por URL de CSV histórico diario, sin API key:
    https://stooq.com/q/d/l/?s=<symbol>&i=d
que se lee con pandas directo.

MURO ANTI-BOT (hallazgo durante integración, documentado en ADR-005): Stooq
introdujo un desafío proof-of-work en JavaScript (calcular un nonce tal que
SHA-256(challenge+nonce) empiece con N ceros hex, y hacer POST a /__verify) antes
de servir el CSV. Este adaptador lo resuelve automáticamente con una sesión
`requests` para preservar el endpoint aprobado. ADVERTENCIA: desde IPs de centros
de datos, Stooq puede responder "Access denied" incluso tras resolver el desafío
(bloqueo por reputación de IP). En ese caso se lanza un error claro y, según
ADR-005, la alternativa aprobada es el índice dólar nativo de Dukascopy.

Salida: esquema canónico OHLC (sin volume ni spread para DXY), índice UTC diario.
"""

from __future__ import annotations

import hashlib
import io
import re
from datetime import datetime

import pandas as pd
import requests

from data import schema
from data.sources.base import DataSource

#: Símbolo del proyecto -> símbolo Stooq.
SYMBOL_MAP: dict[str, str] = {"DXY": "^dxy"}

_BASE_URL = "https://stooq.com/q/d/l/"
_VERIFY_URL = "https://stooq.com/__verify"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


class StooqSource(DataSource):
    """Fuente secundaria Stooq, restringida a DXY diario (ADR-005)."""

    name = "stooq"

    def fetch(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        if symbol not in SYMBOL_MAP:
            raise ValueError(
                f"Stooq solo aprobado para {sorted(SYMBOL_MAP)} (ADR-005); "
                f"pedido {symbol!r}"
            )
        if timeframe != "D1":
            raise ValueError(
                f"Stooq/DXY solo disponible en D1 (ADR-005); pedido {timeframe!r}"
            )

        csv_text = self._download_csv(SYMBOL_MAP[symbol])
        df = self._parse_csv(csv_text)
        return df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]

    # --- descarga con resolución de proof-of-work ---

    def _download_csv(self, stooq_symbol: str) -> str:
        session = requests.Session()
        session.headers["User-Agent"] = _UA
        params = {"s": stooq_symbol, "i": "d"}

        resp = session.get(_BASE_URL, params=params, timeout=30)
        if self._is_challenge(resp.text):
            self._solve_challenge(session, resp.text)
            resp = session.get(_BASE_URL, params=params, timeout=30)

        if self._is_challenge(resp.text) or "Access denied" in resp.text:
            raise RuntimeError(
                "Stooq bloqueó la descarga (muro anti-bot / Access denied). "
                "Desde esta red no es accesible. Alternativa aprobada: índice "
                "dólar nativo de Dukascopy (ADR-005)."
            )
        return resp.text

    @staticmethod
    def _is_challenge(text: str) -> bool:
        return "__verify" in text and "crypto.subtle.digest" in text

    @staticmethod
    def _solve_challenge(session: requests.Session, html: str) -> None:
        """Resuelve el PoW: halla nonce y hace POST a /__verify (misma sesión)."""
        c = re.search(r'c="([^"]+)"', html).group(1)
        difficulty = int(re.search(r"d=(\d+)", html).group(1))
        target = "0" * difficulty
        nonce = 0
        while not hashlib.sha256(f"{c}{nonce}".encode()).hexdigest().startswith(target):
            nonce += 1
        session.post(
            _VERIFY_URL,
            data={"c": c, "n": nonce},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )

    # --- normalización al esquema canónico ---

    @staticmethod
    def _parse_csv(csv_text: str) -> pd.DataFrame:
        """Convierte el CSV de Stooq (Date,Open,High,Low,Close[,Volume]) al canónico.

        Barras diarias: el timestamp se fija al inicio del día en UTC (00:00Z).
        DXY no trae volumen confiable, así que no se incluye la columna volume.
        """
        raw = pd.read_csv(io.StringIO(csv_text))
        rename = {
            "Date": schema.TIMESTAMP,
            "Open": schema.OPEN,
            "High": schema.HIGH,
            "Low": schema.LOW,
            "Close": schema.CLOSE,
        }
        raw = raw.rename(columns=rename)
        raw[schema.TIMESTAMP] = pd.to_datetime(raw[schema.TIMESTAMP], utc=True)
        out = raw.set_index(schema.TIMESTAMP)[
            [schema.OPEN, schema.HIGH, schema.LOW, schema.CLOSE]
        ].sort_index()
        return out
