"""
core/parser.py
--------------
Fasad tingkat tinggi (Facade) untuk membaca dan menormalisasi berkas input rekonsiliasi.
Mendelegasikan proses deteksi dan parsing ke arsitektur adapter terpadu (core.parsers.registry).
Mempertahankan backward-compatibility 100% untuk modul-modul yang memanggil parse_file().
"""

import io
import pandas as pd
from typing import Tuple, List, Union, Any, Optional

from core.models import SourceChannel
from core.parsers.base import clean_number, clean_date, load_dataframe
from core.parsers.registry import default_registry, ParserRegistry

def detect_channel(df: pd.DataFrame) -> SourceChannel:
    """Mendeteksi jenis kanal berdasarkan nama kolom melalui registry parser."""
    for parser in default_registry._parsers.values():
        if parser.detect_format(df=df):
            return parser.source_channel
    return SourceChannel.UNKNOWN

def parse_file(source: Union[str, io.BytesIO, bytes], filename: str = "") -> Tuple[SourceChannel, List[Any]]:
    """
    Membaca berkas CSV, Excel, atau PDF dan mengonversinya ke list of models terstandarisasi
    menggunakan adapter parser yang sesuai.
    """
    return default_registry.detect_and_parse(source, filename)

__all__ = [
    "parse_file",
    "clean_number",
    "clean_date",
    "detect_channel",
    "default_registry",
    "ParserRegistry"
]
