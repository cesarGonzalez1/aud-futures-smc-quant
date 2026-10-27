"""Versionado de datos por manifest + sha256 (sección 10).

Cada archivo Parquet (crudo o derivado) se acompaña de un `manifest.json` en la
misma carpeta. La identidad de una "versión de dataset" es el sha256 del Parquet,
NO una fecha ni un número informal. Los experimentos (sección 12) referencian ese
sha256; un dataset derivado referencia el sha256 del crudo del que proviene,
permitiendo trazar la cadena completa crudo -> features -> resultado.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from data import schema

MANIFEST_NAME = "manifest.json"
_HASH_CHUNK = 1 << 20  # 1 MiB


def sha256_file(path: str | Path) -> str:
    """Calcula el sha256 de un archivo leyéndolo por bloques.

    Args:
        path: ruta al archivo (ej. el .parquet).

    Returns:
        Digest hexadecimal en minúsculas.

    Raises:
        FileNotFoundError: si el archivo no existe.
    """
    path = Path(path)
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_HASH_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class Manifest:
    """Metadatos de versión de un dataset (sección 10).

    Attributes:
        source: fuente de datos ("dukascopy", "stooq", "rates_curated", o
            "derived" para features).
        symbol: símbolo del instrumento (ej. "AUDUSD").
        timeframe: timeframe (ej. "H1"); "" para series sin timeframe.
        date_range: [inicio, fin] en ISO date (str), rango cubierto por el dato.
        download_timestamp: ISO 8601 UTC de cuándo se generó el archivo.
        sha256: hash del archivo Parquet que este manifest describe.
        row_count: número de filas del dataset.
        parent_sha256: sha256 del dataset del que deriva (None si es crudo).
        role: rol del instrumento (ADR-006): "real", "proxy" o "context".
    """

    source: str
    symbol: str
    timeframe: str
    date_range: tuple[str, str]
    download_timestamp: str
    sha256: str
    row_count: int
    parent_sha256: str | None = None
    role: str = schema.ROLE_CONTEXT

    def to_json(self) -> str:
        """Serializa el manifest a JSON indentado y estable."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "Manifest":
        """Reconstruye un Manifest desde su JSON."""
        data = json.loads(text)
        data["date_range"] = tuple(data["date_range"])
        return cls(**data)

    def write(self, directory: str | Path) -> Path:
        """Escribe el manifest como manifest.json en `directory`.

        Returns:
            Ruta del manifest escrito.
        """
        out = Path(directory) / MANIFEST_NAME
        out.write_text(self.to_json(), encoding="utf-8")
        return out


def read_manifest(directory: str | Path) -> Manifest:
    """Lee el manifest.json de un directorio de dataset.

    Raises:
        FileNotFoundError: si no hay manifest en el directorio.
    """
    path = Path(directory) / MANIFEST_NAME
    return Manifest.from_json(path.read_text(encoding="utf-8"))


def verify(directory: str | Path, parquet_name: str) -> bool:
    """Verifica que el sha256 del manifest coincide con el Parquet en disco.

    Base del test de reproducibilidad (sección 13): si el hash no coincide, el
    dato fue alterado fuera del pipeline y no se considera válido.

    Args:
        directory: carpeta que contiene el manifest y el parquet.
        parquet_name: nombre del archivo parquet a verificar.

    Returns:
        True si el hash coincide, False en caso contrario.
    """
    manifest = read_manifest(directory)
    actual = sha256_file(Path(directory) / parquet_name)
    return actual == manifest.sha256
