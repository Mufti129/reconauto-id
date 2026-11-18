"""
core/parser.py
--------------
Fasad tingkat tinggi (Facade) untuk membaca dan menormalisasi berbagai format berkas input rekonsiliasi:
- CSV (koma ',', titik koma ';', tab '\\t', pipe '|') & TSV/TXT
- Excel (.xlsx, .xls) Single-Sheet & Multi-Sheet Workbook
- PDF e-Statement Perbankan (.pdf)
- SWIFT MT940 (.sta, .mt940, .swift)
- ISO 20022 CAMT.053 XML & OFX/QFX (.xml, .camt053, .ofx, .qfx)
- JSON Array, Nested API Payload & JSON Lines (.json, .jsonl, .ndjson)
- Bundel Arsip ZIP Multi-Berkas (.zip)
- Universal Smart Adaptive Fallback untuk skema ERP / Kustom
"""

import io
import pandas as pd
from dataclasses import asdict, is_dataclass
from typing import Tuple, List, Union, Dict, Any, Optional

from core.models import SourceChannel
from core.parsers.base import clean_number, clean_date, load_dataframe
from core.parsers.registry import default_registry, ParserRegistry


def detect_channel(df: pd.DataFrame) -> SourceChannel:
    """Mendeteksi jenis kanal berdasarkan nama kolom melalui registry parser."""
    for parser in default_registry._parsers.values():
        if parser.detect_format(df=df):
            return parser.source_channel
    return SourceChannel.UNKNOWN


def parse_file(source: Union[str, io.BytesIO, bytes, pd.DataFrame], filename: str = "") -> Tuple[SourceChannel, List[Any]]:
    """
    Membaca berkas CSV, TSV, Excel, PDF, JSON, XML, MT940, OFX, atau CAMT.053 dan
    mengonversinya ke list of models terstandarisasi menggunakan adapter parser yang sesuai.
    """
    return default_registry.detect_and_parse(source, filename)


def parse_multi_source(source: Union[str, io.BytesIO, bytes, pd.DataFrame], filename: str = "") -> List[Tuple[SourceChannel, List[Any], str]]:
    """
    Membaca berkas tunggal, arsip bundel .zip, maupun workbook Excel .xlsx multi-sheet,
    dan mengembalikan list of (SourceChannel, records, source_label).
    """
    return default_registry.parse_multi_source(source, filename)


def inspect_file_format(source: Union[str, io.BytesIO, bytes], filename: str = "") -> Dict[str, Any]:
    """
    Menginspeksi struktur berkas input apa pun dan mengembalikan ringkasan deteksi kanal,
    jumlah entitas/sheet yang diekstrak, tipe model kanonikal, serta sampel 5 baris pertama.
    """
    extracted = default_registry.parse_multi_source(source, filename=filename)
    segments = []
    total_records = 0

    for ch, records, label in extracted:
        total_records += len(records)
        sample_rows = []
        for item in records[:5]:
            if is_dataclass(item):
                d = asdict(item)
                d.pop("raw_data", None)
                sample_rows.append(d)
            elif isinstance(item, dict):
                sample_rows.append(item)
            else:
                sample_rows.append(str(item))

        record_type = type(records[0]).__name__ if records else "Empty"
        segments.append({
            "source_label": label,
            "detected_channel": ch.value,
            "record_type": record_type,
            "record_count": len(records),
            "sample_records": sample_rows
        })

    return {
        "filename": filename,
        "recognized": len(segments) > 0 and total_records > 0,
        "segments_count": len(segments),
        "total_records": total_records,
        "segments": segments
    }


__all__ = [
    "parse_file",
    "parse_multi_source",
    "inspect_file_format",
    "clean_number",
    "clean_date",
    "detect_channel",
    "default_registry",
    "ParserRegistry"
]
