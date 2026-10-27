"""Tests de versionado y reproducibilidad (sección 10, 13)."""

from __future__ import annotations

from datetime import datetime, timezone

from data.storage import manifest as m
from data.storage import parquet_store


def test_write_read_roundtrip(clean_h1, tmp_path):
    ts = datetime(2026, 7, 1, tzinfo=timezone.utc).isoformat()
    written = parquet_store.write_dataset(
        clean_h1, base=tmp_path, source="test", symbol="AUDUSD",
        timeframe="H1", download_timestamp=ts,
    )
    directory = parquet_store.dataset_dir(tmp_path, "AUDUSD", "H1")
    read_back = m.read_manifest(directory)
    assert read_back == written
    assert read_back.row_count == len(clean_h1)


def test_verify_detects_tampering(clean_h1, tmp_path):
    ts = datetime(2026, 7, 1, tzinfo=timezone.utc).isoformat()
    parquet_store.write_dataset(
        clean_h1, base=tmp_path, source="test", symbol="AUDUSD",
        timeframe="H1", download_timestamp=ts,
    )
    directory = parquet_store.dataset_dir(tmp_path, "AUDUSD", "H1")
    assert m.verify(directory, parquet_store.PARQUET_NAME)

    # Alterar el parquet debe romper la verificación de hash.
    (directory / parquet_store.PARQUET_NAME).write_bytes(b"corrupted")
    assert not m.verify(directory, parquet_store.PARQUET_NAME)


def test_reproducibility_same_data_same_hash(clean_h1, tmp_path):
    ts = datetime(2026, 7, 1, tzinfo=timezone.utc).isoformat()
    a = parquet_store.write_dataset(
        clean_h1, base=tmp_path / "a", source="test", symbol="AUDUSD",
        timeframe="H1", download_timestamp=ts,
    )
    b = parquet_store.write_dataset(
        clean_h1, base=tmp_path / "b", source="test", symbol="AUDUSD",
        timeframe="H1", download_timestamp=ts,
    )
    assert a.sha256 == b.sha256
