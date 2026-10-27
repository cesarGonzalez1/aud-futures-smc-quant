"""Adaptador Yahoo Finance para futuros — 6A (dólar australiano CME) y 6N
(dólar neozelandés CME), reales (no proxy).

Hasta ADR-016 esta fuente solo traía D1. ADR-018 la extiende a intradía real:
M1, M5, H1 (nativos de `yfinance`) y H4 (derivado por resample desde H1 — Yahoo
no tiene intervalo nativo de 4 horas). Esto es distinto de usar AUDUSD/Dukascopy
como proxy (ADR-006): aquí es el futuro 6A/6N real, pero con INVESTIGACIÓN
HONESTA de que la profundidad histórica intradía gratuita es muy limitada:

    M1  -> últimos 30 días calendario (Yahoo solo permite pedir en bloques de
            máx. 7 días para este intervalo; el adaptador los encadena)
    M5  -> últimos 60 días calendario
    H1  -> últimos ~725 días calendario (~2 años; Yahoo documenta 730, pero pedir
            exactamente 730 falla en la práctica — "must be within the last 730
            days" es estrictamente menor que, no menor-o-igual — se deja margen)
    H4  -> igual límite que H1 (se deriva de H1 por resample, no es un pull nuevo)
    D1  -> histórico completo (sin límite conocido para futuros continuos)

Si se pide un rango más largo que el límite, el adaptador RECORTA el inicio
automáticamente y lo dice explícitamente (no falla en silencio ni finge tener
más historia de la que Yahoo realmente entrega) — sección 16: ambigüedad o
limitación de datos se declara, no se oculta.

**Por qué esto no reemplaza al proxy de Dukascopy (ADR-006):** con solo 30-730
días de historia intradía real, no alcanza para los backtests de 5 años de
V1-V11. Su valor es distinto: (a) cruzar/validar que el proxy AUDUSD se mueve
igual que el 6A real en el periodo reciente que sí se solapa, y (b) alimentar
el motor de señales en modo VIVO (ADR-017/decision_engine), donde solo importa
la barra de hoy, no 5 años de historia.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from data import schema
from data.sources.base import DataSource

#: Símbolo del proyecto -> ticker Yahoo.
SYMBOL_MAP: dict[str, str] = {"6A": "6A=F", "6N": "6N=F"}

#: Timeframe del proyecto -> (intervalo yfinance, límite de días hacia atrás
#: que Yahoo realmente sirve, tamaño máximo de bloque por request en días).
#: `None` en el límite = sin límite conocido (D1).
_INTRADAY_SPEC: dict[str, tuple[str, int | None, int | None]] = {
    "M1": ("1m", 30, 7),
    "M5": ("5m", 60, None),
    "H1": ("60m", 725, None),  # Yahoo documenta "730" pero pedir EXACTO 730 falla en la práctica
                                # ("must be within the last 730 days" es estrictamente <, no <=) — margen de 5 días
    # H4 no es nativo de yfinance: se pide H1 y se resamplea abajo.
}

SUPPORTED_TIMEFRAMES: tuple[str, ...] = ("M1", "M5", "H1", "H4", "D1")


class YahooFuturesSource(DataSource):
    """Fuente de futuros CME vía yfinance (activo real, ADR-006 + ADR-018)."""

    name = "yahoo_futures"
    role = schema.ROLE_REAL

    def fetch(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        if symbol not in SYMBOL_MAP:
            raise ValueError(
                f"Símbolo {symbol!r} no mapeado para Yahoo futures. "
                f"Soportados: {sorted(SYMBOL_MAP)}"
            )
        if timeframe not in SUPPORTED_TIMEFRAMES:
            raise ValueError(
                f"Timeframe {timeframe!r} no soportado por Yahoo futures. "
                f"Soportados: {SUPPORTED_TIMEFRAMES}"
            )

        ticker = SYMBOL_MAP[symbol]
        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
        if start_ts.tz is None:
            start_ts = start_ts.tz_localize("UTC")
        else:
            start_ts = start_ts.tz_convert("UTC")
        if end_ts.tz is None:
            end_ts = end_ts.tz_localize("UTC")
        else:
            end_ts = end_ts.tz_convert("UTC")

        if timeframe == "D1":
            return self._fetch_daily(ticker, start_ts, end_ts)

        base_timeframe = "H1" if timeframe == "H4" else timeframe
        interval, max_lookback_days, chunk_days = _INTRADAY_SPEC[base_timeframe]

        # Yahoo, para intradía, SIEMPRE sirve una ventana que termina en HOY —
        # no un tramo histórico fijo que termine en el pasado, aunque ese "fin"
        # esté técnicamente dentro del límite de días. Por eso el fin efectivo
        # es simplemente "ahora", y el inicio se recorta al límite de Yahoo; si
        # el rango pedido queda ENTERO fuera de esa ventana (su propio fin ya
        # es más viejo que el límite), no hay nada que pedir.
        now = pd.Timestamp.now(tz="UTC")
        floor = now.normalize() - timedelta(days=max_lookback_days) if max_lookback_days is not None else None

        if floor is not None and end_ts < floor:
            print(
                f"[yahoo_futures] {symbol} {timeframe}: pediste hasta {end_ts.date()}, pero eso ya es más "
                f"viejo que los ~{max_lookback_days} días que Yahoo sirve para este intervalo (hoy={now.date()}). "
                f"0 filas — no es un error, Yahoo simplemente ya no tiene esa ventana intradía."
            )
            return self._empty_frame()

        effective_start = max(start_ts, floor) if floor is not None else start_ts
        effective_end = now

        if effective_start != start_ts or end_ts < effective_end:
            print(
                f"[yahoo_futures] Aviso: pediste {symbol} {timeframe} de {start_ts.date()} a {end_ts.date()}, "
                f"pero Yahoo intradía solo sirve una ventana reciente que termina HOY, no un tramo fijo en el "
                f"pasado. Se ajusta a [{effective_start.date()}, {effective_end.date()}]."
            )

        if effective_start >= effective_end:
            return self._empty_frame()

        raw = self._fetch_intraday(ticker, interval, effective_start, effective_end, chunk_days)
        if raw.empty:
            return self._empty_frame()

        df = self._normalize_intraday(raw)
        if timeframe == "H4":
            df = self._resample_h4(df)
        return df

    @staticmethod
    def _fetch_daily(ticker: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.DataFrame:
        import yfinance as yf

        raw = yf.download(
            ticker, start=start_ts.date().isoformat(), end=end_ts.date().isoformat(),
            interval="1d", progress=False, auto_adjust=False,
        )
        if raw is None or raw.empty:
            return YahooFuturesSource._empty_frame()
        return YahooFuturesSource._normalize(raw)

    @staticmethod
    def _fetch_intraday(
        ticker: str, interval: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp, chunk_days: int | None,
    ) -> pd.DataFrame:
        import yfinance as yf

        if chunk_days is None:
            raw = yf.download(
                ticker, start=start_ts.date().isoformat(), end=end_ts.date().isoformat(),
                interval=interval, progress=False, auto_adjust=False,
            )
            return raw if raw is not None else pd.DataFrame()

        # M1: Yahoo exige ventanas <= 7 días por request -> se encadenan.
        parts = []
        cursor = start_ts
        while cursor < end_ts:
            chunk_end = min(cursor + timedelta(days=chunk_days), end_ts)
            raw = yf.download(
                ticker, start=cursor.date().isoformat(), end=chunk_end.date().isoformat(),
                interval=interval, progress=False, auto_adjust=False,
            )
            if raw is not None and not raw.empty:
                parts.append(raw)
            cursor = chunk_end
        if not parts:
            return pd.DataFrame()
        return pd.concat(parts).sort_index()

    @staticmethod
    def _normalize(raw: pd.DataFrame) -> pd.DataFrame:
        df = raw.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        rename = {
            "Open": schema.OPEN, "High": schema.HIGH, "Low": schema.LOW,
            "Close": schema.CLOSE, "Volume": schema.VOLUME,
        }
        df = df.rename(columns=rename)[list(rename.values())]
        idx = pd.to_datetime(df.index)
        idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
        df.index = idx
        df.index.name = schema.TIMESTAMP
        return df.sort_index().dropna(how="all")

    @staticmethod
    def _normalize_intraday(raw: pd.DataFrame) -> pd.DataFrame:
        return YahooFuturesSource._normalize(raw)

    @staticmethod
    def _resample_h4(df_h1: pd.DataFrame) -> pd.DataFrame:
        """Deriva H4 desde H1 (Yahoo no tiene intervalo nativo de 4h)."""
        agg = {schema.OPEN: "first", schema.HIGH: "max", schema.LOW: "min",
               schema.CLOSE: "last", schema.VOLUME: "sum"}
        out = df_h1.resample("4h").agg(agg).dropna(subset=[schema.OPEN])
        out.index.name = schema.TIMESTAMP
        return out

    @staticmethod
    def _empty_frame() -> pd.DataFrame:
        cols = [schema.OPEN, schema.HIGH, schema.LOW, schema.CLOSE, schema.VOLUME]
        idx = pd.DatetimeIndex([], tz="UTC", name=schema.TIMESTAMP)
        # dtype float64 explícito: un DataFrame vacío sin esto queda con dtype
        # 'object' y el check de calidad lo marca como "columna no numérica" —
        # falso positivo, 0 filas por rango fuera de la ventana de Yahoo no es
        # un fallo de calidad.
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in cols}, index=idx)
