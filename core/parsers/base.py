"""
core/parsers/base.py
-------------------
Kontrak antarmuka abstrak (Interface/Strategy) untuk seluruh adapter parser kanal sumber.
"""

import re
import io
import pandas as pd
from abc import ABC, abstractmethod
from typing import Tuple, List, Union, Dict, Any, Optional
from core.models import SourceChannel, CanonicalTransaction, BankStatementRow, CodSettlementRow

def clean_number(val: Any) -> float:
    """Mengubah berbagai format teks mata uang (Rp, titik, koma) menjadi float."""
    if val is None or pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s == "-":
        return 0.0
    
    # Hapus prefix non-angka selain titik, koma, dan minus
    s = re.sub(r"[^\d,\.\-]", "", s)
    
    # Format Indonesia: 1.500.000,00 atau 1.500.000
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            # Koma adalah desimal: 1.500.000,50
            s = s.replace(".", "").replace(",", ".")
        else:
            # Titik adalah desimal: 1,500,000.50
            s = s.replace(",", "")
    elif "," in s:
        # Hanya ada koma: bisa desimal atau pemisah ribuan
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    
    try:
        return float(s)
    except ValueError:
        return 0.0

def clean_date(val: Any) -> str:
    """Mengonversi berbagai format tanggal ke format ISO YYYY-MM-DD."""
    if val is None or pd.isna(val):
        return ""
    s = str(val).strip()
    # Jika ada waktu (e.g. 2026-08-01 14:30:00), ambil tanggalnya saja
    if " " in s:
        s = s.split(" ")[0]
    
    # Normalisasi tanda strip dan slash
    parts = re.split(r"[\/\-\.]", s)
    if len(parts) == 3:
        p1, p2, p3 = parts
        if len(p1) == 4:  # YYYY-MM-DD
            return f"{p1}-{p2.zfill(2)}-{p3.zfill(2)}"
        elif len(p3) == 4:  # DD-MM-YYYY
            return f"{p3}-{p2.zfill(2)}-{p1.zfill(2)}"
    return s

def load_dataframe(source: Union[str, io.BytesIO, bytes], filename: str = "") -> pd.DataFrame:
    """Helper seragam untuk membaca file CSV atau Excel menjadi DataFrame pandas."""
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    elif isinstance(source, str) and not os.path.exists(source):
        source = io.StringIO(source)
        
    fn_lower = filename.lower()
    if fn_lower.endswith(".xlsx") or fn_lower.endswith(".xls"):
        df = pd.read_excel(source)
    else:
        try:
            df = pd.read_csv(source, encoding="utf-8")
        except UnicodeDecodeError:
            if hasattr(source, "seek"):
                source.seek(0)
            df = pd.read_csv(source, encoding="latin1")
            
    df.columns = [str(c).strip() for c in df.columns]
    return df

class BaseChannelParser(ABC):
    """Kelas abstrak dasar untuk seluruh parser adapter kanal finansial."""

    @property
    @abstractmethod
    def channel_id(self) -> str:
        """Pengenal unik kanal, misal: 'BANK_BCA', 'LOGISTICS_JNE_COD'."""
        pass

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Nama manusiawi kanal, misal: 'Bank BCA KlikBCA / MCM'."""
        pass

    @property
    @abstractmethod
    def source_channel(self) -> SourceChannel:
        """Nilai Enum SourceChannel."""
        pass

    @abstractmethod
    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        """Mendeteksi apakah berkas cocok dengan adapter parser ini."""
        pass

    @abstractmethod
    def parse(self, source: Union[str, io.BytesIO, bytes], filename: str = "") -> Tuple[SourceChannel, List[Any]]:
        """Membaca berkas dan mengembalikan tuple (SourceChannel, list_of_records)."""
        pass

    def classify_channel_type(self) -> str:
        """BANK, MARKETPLACE, PAYMENT_GATEWAY, POS, LOGISTICS_COD."""
        ch_val = self.source_channel.value
        if "BANK" in ch_val:
            return "BANK"
        elif "MARKETPLACE" in ch_val:
            return "MARKETPLACE"
        elif "GATEWAY" in ch_val:
            return "PAYMENT_GATEWAY"
        elif "POS" in ch_val:
            return "POS"
        elif "LOGISTICS" in ch_val or "COD" in ch_val:
            return "LOGISTICS_COD"
        return "UNKNOWN"

    def get_matching_strategy(self) -> str:
        """Mengembalikan strategi pencocokan: 'BATCH_BASED', 'REFERENCE_BASED', 'COD_THREE_WAY'."""
        ctype = self.classify_channel_type()
        if ctype == "LOGISTICS_COD":
            return "COD_THREE_WAY"
        elif ctype == "BANK":
            return "REFERENCE_BASED"
        return "BATCH_BASED"
