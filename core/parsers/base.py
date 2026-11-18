"""
core/parsers/base.py
--------------------
Kontrak antarmuka abstrak (Interface/Strategy) untuk seluruh adapter parser kanal sumber,
dilengkapi dengan Universal Data Loader multi-format:
- CSV (koma ',', titik koma ';', tab '\\t', pipe '|') dengan deteksi delimiter & encoding otomatis
- Excel (.xlsx, .xls) termasuk deteksi baris header otomatis (melewati baris metadata di atas tabel)
- JSON & NDJSON/JSONL (.json, .jsonl, .ndjson) baik array langsung maupun nested payload API
- XML / HTML Table (.xml, .xls berbasis HTML)
- Normalisasi angka akuntansi (tanda kurung negatif, Rp/IDR, format Indonesia & Internasional)
- Normalisasi tanggal multi-bahasa (ISO, DD/MM/YYYY, nama bulan Indonesia/Inggris, serial Excel)
"""

import os
import re
import io
import csv
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from typing import Tuple, List, Union, Dict, Any, Optional
import pandas as pd

from core.models import SourceChannel, CanonicalTransaction, BankStatementRow, CodSettlementRow

# Pemetaan nama bulan Indonesia & Inggris ke angka bulan (01-12)
_MONTH_MAP = {
    "jan": "01", "januari": "01", "january": "01",
    "feb": "02", "februari": "02", "february": "02",
    "mar": "03", "maret": "03", "march": "03",
    "apr": "04", "april": "04",
    "mei": "05", "may": "05",
    "jun": "06", "juni": "06", "june": "06",
    "jul": "07", "juli": "07", "july": "07",
    "agu": "08", "ags": "08", "agustus": "08", "aug": "08", "august": "08",
    "sep": "09", "sept": "09", "september": "09",
    "okt": "10", "oktober": "10", "oct": "10", "october": "10",
    "nov": "11", "nop": "11", "november": "11", "nopember": "11",
    "des": "12", "desember": "12", "dec": "12", "december": "12",
}

# Kata kunci penanda baris header tabel pada berkas rekening koran / laporan marketplace
_HEADER_KEYWORDS = {
    "tanggal", "tgl", "date", "waktu", "time", "post date", "value date", "settlement",
    "keterangan", "description", "uraian", "remark", "narasi", "memo",
    "jumlah", "amount", "nominal", "mutasi", "gross", "net", "total", "nilai",
    "saldo", "balance", "debit", "debet", "kredit", "credit", "tipe", "db/cr",
    "order", "invoice", "pesanan", "trx", "transaction", "reference", "ref",
    "awb", "resi", "waybill", "cod", "receipt", "outlet", "rrn", "nmid"
}


def clean_number(val: Any) -> float:
    """
    Mengubah berbagai format teks mata uang & akuntansi menjadi float:
    - Format Indonesia: 'Rp 1.500.000,50', '1.250.000,-', '1.500.000'
    - Format Internasional: 'IDR 1,500,000.50', '$1,200.00'
    - Format Akuntansi Negatif: '(1.500.000)', '(250,000.00)', '1.500.000-'
    - Sufiks DB/CR: '1.500.000,00 CR', '50.000 DB'
    """
    if val is None or pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s or s in ("-", "--", "N/A", "null", "None", "nan"):
        return 0.0

    # Deteksi tanda kurung akuntansi negatif: (1.500.000) atau (250,000)
    is_negative = False
    if (s.startswith("(") and s.endswith(")")) or s.endswith("-"):
        is_negative = True
        s = s.strip("()- ")

    # Bersihkan sufiks khusus Indonesia ',-' atau ',00-'
    s = re.sub(r",-\s*$", "", s)
    s = re.sub(r"\.-\s*$", "", s)

    # Hapus karakter non-angka selain titik, koma, dan minus
    s = re.sub(r"[^\d,\.\-]", "", s)
    if not s or s == "-":
        return 0.0

    if s.startswith("-"):
        is_negative = True
        s = s.lstrip("-")

    # Analisis pemisah ribuan vs desimal
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            # Format Indonesia: 1.500.000,50 (koma adalah desimal)
            s = s.replace(".", "").replace(",", ".")
        else:
            # Format Inggris/US: 1,500,000.50 (titik adalah desimal)
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            # Koma sebagai desimal: 1500000,50
            s = s.replace(",", ".")
        else:
            # Koma sebagai pemisah ribuan: 1,500,000 atau 1,500
            s = s.replace(",", "")
    elif "." in s:
        parts = s.split(".")
        # Jika ada lebih dari 1 titik (misal 1.500.000) atau tepat 3 digit di belakang titik ribuan (misal 500.000)
        if len(parts) > 2:
            # Jika segmen terakhir panjangnya <= 2, bisa jadi desimal aneh, tapi umumnya 1.500.000 adalah ribuan
            if len(parts[-1]) <= 2:
                s = "".join(parts[:-1]) + "." + parts[-1]
            else:
                s = "".join(parts)
        elif len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) >= 1:
            # Contoh: '500.000' pada konteks Rupiah adalah 500 ribu
            s = s.replace(".", "")

    try:
        result = float(s)
        return -result if is_negative else result
    except ValueError:
        return 0.0


def clean_date(val: Any) -> str:
    """
    Mengonversi berbagai format tanggal ke format standar ISO YYYY-MM-DD:
    - ISO / Standar: '2026-08-15', '2026-08-15T14:30:00+07:00', '2026/08/15'
    - Format Indonesia / Eropa: '15/08/2026', '15-08-2026', '15.08.2026', '15/08/26'
    - Nama Bulan (ID/EN): '15 Agu 2026', '15 Agustus 2026', 'Aug 15, 2026', '15-Aug-2026'
    - Angka Serial Tanggal Excel: 46249 -> '2026-08-15'
    """
    if val is None or pd.isna(val):
        return ""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")

    # Tangani Excel serial date number (misal 44000 s/d 55000)
    if isinstance(val, (int, float)) and 30000 <= float(val) <= 60000:
        base_excel = datetime(1899, 12, 30)
        return (base_excel + timedelta(days=int(val))).strftime("%Y-%m-%d")

    s = str(val).strip()
    if not s or s.lower() in ("-", "nan", "nat", "none", "null"):
        return ""

    # Jika angka serial Excel dalam bentuk string
    if s.isdigit() and len(s) == 5 and 30000 <= int(s) <= 60000:
        base_excel = datetime(1899, 12, 30)
        return (base_excel + timedelta(days=int(s))).strftime("%Y-%m-%d")

    # Potong bagian waktu ISO / timestamp (misal '2026-08-15T10:20:30Z' atau '15/08/2026 14:30:00')
    if "T" in s and re.match(r"^\d{4}-\d{2}-\d{2}T", s):
        return s.split("T")[0]

    # Cek format dengan nama bulan teks (misal '15 Agu 2026', '15-Aug-2026', 'Agustus 15, 2026')
    s_clean = re.sub(r"[,]", " ", s)
    tokens = [t for t in re.split(r"[\s\/\-\.]+", s_clean) if t]
    if len(tokens) >= 3:
        # Pola 1: DD <Bulan> YYYY (misal 15 Agustus 2026)
        m1 = _MONTH_MAP.get(tokens[1].lower())
        if m1 and tokens[0].isdigit() and tokens[2].isdigit():
            day = tokens[0].zfill(2)
            year = tokens[2] if len(tokens[2]) == 4 else f"20{tokens[2]}"
            return f"{year}-{m1}-{day}"
        # Pola 2: <Bulan> DD YYYY (misal Aug 15 2026)
        m0 = _MONTH_MAP.get(tokens[0].lower())
        if m0 and tokens[1].isdigit() and tokens[2].isdigit():
            day = tokens[1].zfill(2)
            year = tokens[2] if len(tokens[2]) == 4 else f"20{tokens[2]}"
            return f"{year}-{m0}-{day}"

    # Ambil bagian tanggal saja jika ada jam 'YYYY-MM-DD HH:MM:SS'
    if " " in s:
        s = s.split(" ")[0]

    parts = re.split(r"[\/\-\.]", s)
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        p1, p2, p3 = parts
        if len(p1) == 4:  # YYYY-MM-DD atau YYYY/MM/DD
            return f"{p1}-{p2.zfill(2)}-{p3.zfill(2)}"
        elif len(p3) == 4:  # DD-MM-YYYY atau MM-DD-YYYY
            # Jika p2 > 12, maka p1 adalah MM dan p2 adalah DD (format US MM/DD/YYYY)
            if int(p2) > 12 and int(p1) <= 12:
                return f"{p3}-{p1.zfill(2)}-{p2.zfill(2)}"
            return f"{p3}-{p2.zfill(2)}-{p1.zfill(2)}"
        elif len(p3) == 2 and len(p1) <= 2 and len(p2) <= 2:  # DD/MM/YY
            year = f"20{p3}"
            if int(p2) > 12 and int(p1) <= 12:
                return f"{year}-{p1.zfill(2)}-{p2.zfill(2)}"
            return f"{year}-{p2.zfill(2)}-{p1.zfill(2)}"

    return s


def _score_header_row(cells: List[Any]) -> int:
    """Menghitung skor kecocokan sebuah baris sebagai header tabel transaksi."""
    non_empty = [str(c).strip().lower() for c in cells if c is not None and not pd.isna(c) and str(c).strip()]
    if len(non_empty) < 2:
        return 0
    score = 0
    for cell in non_empty:
        if any(kw in cell for kw in _HEADER_KEYWORDS):
            score += 2
        # Penalti jika sel terlihat seperti nilai angka murni atau tanggal transaksi
        if re.match(r"^[\d,\.\-\(\)\s]+$", cell) or re.match(r"^\d{4}-\d{2}-\d{2}$", cell):
            score -= 1
    return score


def _promote_header_row_if_needed(df: pd.DataFrame) -> pd.DataFrame:
    """
    Jika baris pertama DataFrame adalah metadata (misal 'Nomor Rekening: 123', 'Unnamed: 1'),
    cari baris header tabel yang sebenarnya pada 20 baris pertama dan jadikan sebagai kolom DataFrame.
    """
    if df is None or df.empty:
        return df

    current_cols = [str(c).strip() for c in df.columns]
    unnamed_count = sum(1 for c in current_cols if c.lower().startswith("unnamed:") or not c)
    current_score = _score_header_row(current_cols)

    # Jika kolom saat ini sudah bagus (tidak banyak Unnamed dan memiliki kata kunci header), pertahankan
    if unnamed_count <= len(current_cols) // 3 and current_score >= 4:
        df.columns = current_cols
        return df

    # Pindai hingga 20 baris pertama untuk menemukan baris header terbaik
    best_idx = -1
    best_score = current_score
    max_scan = min(len(df), 20)

    for i in range(max_scan):
        row_vals = df.iloc[i].tolist()
        sc = _score_header_row(row_vals)
        if sc > best_score and sc >= 4:
            best_score = sc
            best_idx = i

    if best_idx >= 0:
        new_cols = []
        for idx_c, val in enumerate(df.iloc[best_idx].tolist()):
            col_name = str(val).strip() if (val is not None and not pd.isna(val) and str(val).strip()) else f"col_{idx_c}"
            new_cols.append(col_name)
        df = df.iloc[best_idx + 1:].reset_index(drop=True)
        df.columns = new_cols

    # Bersihkan baris yang seluruhnya kosong
    df = df.dropna(how="all").reset_index(drop=True)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _load_json_to_dataframe(raw_bytes: bytes) -> pd.DataFrame:
    """Membaca berkas JSON (Array, Nested API Object, atau JSONL/NDJSON) menjadi DataFrame."""
    text = raw_bytes.decode("utf-8-sig", errors="replace").strip()
    if not text:
        return pd.DataFrame()

    # Coba parse sebagai JSON standar terlebih dahulu
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return pd.DataFrame(parsed)
        elif isinstance(parsed, dict):
            # Cari key array yang menyimpan daftar transaksi
            for key in ("data", "transactions", "records", "items", "orders", "settlements", "rows", "mutations", "results"):
                if key in parsed and isinstance(parsed[key], list):
                    return pd.DataFrame(parsed[key])
            # Cari sembarang key bernilai list of dicts
            for val in parsed.values():
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    return pd.DataFrame(val)
            return pd.DataFrame([parsed])
    except json.JSONDecodeError:
        # Coba parse sebagai JSON Lines (NDJSON / .jsonl)
        records = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        records.append(obj)
                except json.JSONDecodeError:
                    continue
        if records:
            return pd.DataFrame(records)
    return pd.DataFrame()


def _load_xml_to_dataframe(raw_bytes: bytes) -> pd.DataFrame:
    """Membaca berkas XML tabel generik menjadi DataFrame."""
    text = raw_bytes.decode("utf-8-sig", errors="replace").strip()
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return pd.DataFrame()

    def _strip_ns(tag: str) -> str:
        return tag.split("}", 1)[-1] if "}" in tag else tag

    rows = []
    # Cari elemen berulang (seperti <Row>, <Transaction>, <Record>, <Item>, <Ntry>)
    children = list(root)
    if len(children) == 1 and len(list(children[0])) > 1:
        children = list(children[0])

    for elem in children:
        row_dict: Dict[str, Any] = {}
        for sub in elem.iter():
            if sub is elem:
                continue
            if len(list(sub)) == 0 and sub.text and sub.text.strip():
                key = _strip_ns(sub.tag)
                if key in row_dict:
                    row_dict[f"{key}_2"] = sub.text.strip()
                else:
                    row_dict[key] = sub.text.strip()
        if row_dict:
            rows.append(row_dict)

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _read_text_with_Detected_delimiter(raw_bytes: bytes) -> pd.DataFrame:
    """
    Membaca berkas CSV/TSV/TXT dengan deteksi encoding (UTF-8-SIG, UTF-8, CP1252, Latin1, UTF-16)
    dan deteksi delimiter otomatis (',', ';', '\\t', '|') serta melewati baris metadata awal.
    """
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin1", "utf-16"):
        try:
            text = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw_bytes.decode("utf-8", errors="replace")

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return pd.DataFrame()

    # Deteksi delimiter terbaik dari 15 baris pertama
    sample_lines = lines[:15]
    candidate_delims = [",", ";", "\t", "|"]
    best_delim = ","
    best_score = -1

    for d in candidate_delims:
        counts = [ln.count(d) for ln in sample_lines if ln.count(d) > 0]
        if counts:
            # Skor berdasarkan konsistensi dan jumlah kolom
            max_c = max(counts)
            score = len(counts) * min(max_c, 15)
            if score > best_score:
                best_score = score
                best_delim = d

    # Cari apakah ada baris metadata di atas baris header
    header_line_idx = 0
    best_hdr_score = -1
    for idx, ln in enumerate(lines[:20]):
        try:
            cells = next(csv.reader([ln], delimiter=best_delim))
        except Exception:
            cells = ln.split(best_delim)
        if len(cells) >= 3:
            sc = _score_header_row(cells)
            if sc > best_hdr_score and sc >= 4:
                best_hdr_score = sc
                header_line_idx = idx
                break

    cleaned_text = "\n".join(lines[header_line_idx:])
    try:
        df = pd.read_csv(io.StringIO(cleaned_text), sep=best_delim, engine="python", on_bad_lines="skip")
    except Exception:
        df = pd.read_csv(io.StringIO(text), sep=None, engine="python", on_bad_lines="skip")

    return _promote_header_row_if_needed(df)


def load_dataframe(source: Union[str, io.BytesIO, bytes, pd.DataFrame], filename: str = "") -> pd.DataFrame:
    """
    Universal DataFrame Loader yang mampu membaca:
    - Objek DataFrame langsung (Zero copy / Tanpa double-parsing)
    - CSV dengan delimiter ',', ';', '\\t' (.tsv), atau '|' (.txt)
    - Excel (.xlsx, .xls) termasuk berkas .xls yang berisi tabel HTML/TSV
    - JSON & NDJSON (.json, .jsonl, .ndjson)
    - XML (.xml)
    Serta otomatis mempromosikan baris header jika terdapat preamble metadata di bagian atas.
    """
    if isinstance(source, pd.DataFrame):
        return _promote_header_row_if_needed(source.copy())

    raw_bytes: Optional[bytes] = None
    if isinstance(source, bytes):
        raw_bytes = source
    elif hasattr(source, "read"):
        if hasattr(source, "seek"):
            source.seek(0)
        content = source.read()
        if hasattr(source, "seek"):
            source.seek(0)
        raw_bytes = content if isinstance(content, bytes) else str(content).encode("utf-8")
    elif isinstance(source, str):
        if os.path.exists(source):
            with open(source, "rb") as f:
                raw_bytes = f.read()
        else:
            raw_bytes = source.encode("utf-8")
    else:
        raw_bytes = str(source).encode("utf-8")

    if not raw_bytes:
        return pd.DataFrame()

    fn_lower = (filename or "").lower().strip()
    head_strip = raw_bytes[:512].lstrip()

    # 1. Deteksi format JSON / JSONL
    if fn_lower.endswith((".json", ".jsonl", ".ndjson")) or head_strip.startswith((b"{", b"[")):
        df_json = _load_json_to_dataframe(raw_bytes)
        if not df_json.empty:
            df_json.columns = [str(c).strip() for c in df_json.columns]
            return df_json

    # 2. Deteksi format XML
    if fn_lower.endswith((".xml", ".camt053")) or (head_strip.startswith(b"<?xml") and b"<Workbook" not in head_strip):
        df_xml = _load_xml_to_dataframe(raw_bytes)
        if not df_xml.empty:
            df_xml.columns = [str(c).strip() for c in df_xml.columns]
            return df_xml

    # 3. Deteksi format Excel (.xlsx / .xls) atau ZIP PK header (XLSX)
    if fn_lower.endswith((".xlsx", ".xls")) or head_strip.startswith(b"PK\x03\x04"):
        try:
            df_excel = pd.read_excel(io.BytesIO(raw_bytes))
            return _promote_header_row_if_needed(df_excel)
        except Exception:
            # Banyak bank di Indonesia mengekspor file berekstensi .xls yang isinya sebenarnya TSV atau CSV!
            return _read_text_with_Detected_delimiter(raw_bytes)

    # 4. Default: CSV / TSV / TXT dengan auto-delimiter & header promotion
    return _read_text_with_Detected_delimiter(raw_bytes)


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
    def parse(self, source: Union[str, io.BytesIO, bytes, pd.DataFrame], filename: str = "") -> Tuple[SourceChannel, List[Any]]:
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
