"""
core/parsers/base.py
--------------------
Kontrak antarmuka abstrak (Interface/Strategy) dan Universal Multi-Format Data Loader:
Mendukung akomodasi perbedaan format input secara menyeluruh tanpa terkendala:
1. Delimited Text (.csv, .tsv, .tab, .txt, .dat, .prn):
   - Auto-detect delimiter: koma (','), titik koma (';'), tab ('\\t'), pipe ('|'), caret ('^'), tilde ('~')
   - Fixed-width / Spasi ganda (2+ spaces) dari spool AS400 / Core Banking
   - Auto-detect encoding: UTF-8-SIG (BOM), UTF-8, CP1252, Latin-1, UTF-16
   - Smart Header Discovery: melewati 1-30 baris kop/metadata di atas tabel & membuang baris Total/Subtotal di bawah
2. Spreadsheet & Workbook (.xlsx, .xls, .ods, .html, .htm):
   - Excel modern (.xlsx) & legacy (.xls) Single-Sheet maupun Multi-Sheet
   - Fake .xls berbasis HTML <table> (umum pada KlikBCA Bisnis, BRI, Mandiri, Accurate)
   - Fake .xls berbasis XML SpreadsheetML 2003 (<Workbook><Worksheet><Table><Row><Cell><Data>)
3. Columnar & Compressed Data (.parquet, .pq, .feather, .gz, .csv.gz, .json.gz):
   - Apache Parquet & Feather (via pyarrow)
   - Dekompresi Gzip otomatis di memori
4. JSON & Open Banking API (.json, .jsonl, .ndjson):
   - JSON Array, Nested Webhook Payload, Pandas orient='split'/'columns'/'index'
   - Flattening otomatis objek bersarang standar SNAP BI (misal amount: {"value": "150000.00", "currency": "IDR"})
5. Normalisasi Angka & Tanggal Ekstrem:
   - Angka akuntansi: '(1.500.000,00)', '1.500.000-', 'Rp 1.250.000,-', '1.500.000,00 DB', '500,000.00 CR'
   - Tanggal: ISO, DD/MM/YYYY, MM/DD/YYYY, DD/MM tanpa tahun ('15/08'), 'PEND' (KlikBCA), tanggal 8-digit ('20260815'),
     nama bulan Indonesia & Inggris ('15 Agu 2026', 'Aug 15, 2026'), Excel serial date ('46249'), dan Unix Epoch timestamp.
"""

import os
import re
import io
import csv
import gzip
import json
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from datetime import datetime, timedelta, timezone
from abc import ABC, abstractmethod
from typing import Tuple, List, Union, Dict, Any, Optional
import pandas as pd

from core.models import SourceChannel, CanonicalTransaction, BankStatementRow, CodSettlementRow

# Pemetaan nama bulan Indonesia & Inggris ke angka bulan (01-12)
_MONTH_MAP = {
    "jan": "01", "januari": "01", "january": "01",
    "feb": "02", "februari": "02", "february": "02", "peb": "02", "pebruari": "02",
    "mar": "03", "maret": "03", "march": "03", "mrt": "03",
    "apr": "04", "april": "04",
    "mei": "05", "may": "05",
    "jun": "06", "juni": "06", "june": "06",
    "jul": "07", "juli": "07", "july": "07",
    "agu": "08", "ags": "08", "agust": "08", "agustus": "08", "aug": "08", "august": "08",
    "sep": "09", "sept": "09", "september": "09",
    "okt": "10", "oktober": "10", "oct": "10", "october": "10",
    "nov": "11", "nop": "11", "november": "11", "nopember": "11",
    "des": "12", "desember": "12", "dec": "12", "december": "12",
}

# Kata kunci penanda baris header tabel pada berkas rekening koran / laporan marketplace / ERP
_HEADER_KEYWORDS = {
    "tanggal", "tgl", "date", "waktu", "time", "post date", "posting date", "value date", "settlement",
    "keterangan", "description", "uraian", "remark", "remarks", "narasi", "narration", "memo", "berita",
    "jumlah", "amount", "nominal", "mutasi", "gross", "net", "total", "nilai", "harga", "price",
    "saldo", "balance", "debit", "debet", "kredit", "credit", "tipe", "type", "db/cr", "d/c",
    "order", "invoice", "pesanan", "trx", "txn", "transaction", "reference", "ref", "faktur", "nota",
    "awb", "resi", "waybill", "connote", "cod", "receipt", "outlet", "rrn", "nmid", "kasir", "sku"
}

# Kata kunci baris ringkasan / footer yang bukan merupakan baris transaksi
_SUMMARY_ROW_PATTERNS = (
    "SALDO AWAL", "SALDO AKHIR", "OPENING BALANCE", "CLOSING BALANCE",
    "ENDING BALANCE", "BEGINNING BALANCE", "TOTAL MUTASI", "SUBTOTAL",
    "GRAND TOTAL", "JUMLAH TOTAL", "CATATAN:", "DISCLAIMER"
)


class _SimpleHTMLTableParser(HTMLParser):
    """Parser ringan untuk mengekstrak tabel dari berkas .xls / .html yang berisi tag <table> HTML."""

    def __init__(self):
        super().__init__()
        self.tables: List[List[List[str]]] = []
        self._curr_table: Optional[List[List[str]]] = None
        self._curr_row: Optional[List[str]] = None
        self._curr_cell: Optional[List[str]] = None

    def handle_starttag(self, tag: str, attrs: list):
        t = tag.lower()
        if t == "table":
            self._curr_table = []
        elif t == "tr" and self._curr_table is not None:
            self._curr_row = []
        elif t in ("td", "th") and self._curr_row is not None:
            self._curr_cell = []

    def handle_data(self, data: str):
        if self._curr_cell is not None:
            self._curr_cell.append(data)

    def handle_endtag(self, tag: str):
        t = tag.lower()
        if t in ("td", "th") and self._curr_cell is not None and self._curr_row is not None:
            self._curr_row.append(" ".join("".join(self._curr_cell).split()).strip())
            self._curr_cell = None
        elif t == "tr" and self._curr_row is not None and self._curr_table is not None:
            if any(c for c in self._curr_row):
                self._curr_table.append(self._curr_row)
            self._curr_row = None
        elif t == "table" and self._curr_table is not None:
            if self._curr_table:
                self.tables.append(self._curr_table)
            self._curr_table = None


def extract_amount_and_sign(val: Any) -> Tuple[float, Optional[str]]:
    """
    Mengekstrak nilai float beserta indikator eksplisit DB/CR dari string nominal (jika ada).
    Contoh:
      '1.500.000,00 DB' -> (-1500000.0, 'DB')
      '2.450.000,00 CR' -> (2450000.0, 'CR')
      '(250.000)'       -> (-250000.0, 'DB')
    """
    if val is None or pd.isna(val):
        return 0.0, None
    if isinstance(val, (int, float)):
        f = float(val)
        return f, ("DB" if f < 0 else None)

    s = str(val).strip()
    if not s:
        return 0.0, None

    explicit_dir: Optional[str] = None
    m_dir = re.search(r"\b(DB|DR|DEBIT|DEBET|CR|KREDIT|CREDIT|D|C)\s*$", s, flags=re.IGNORECASE)
    if not m_dir:
        m_dir = re.search(r"^\s*(DB|DR|DEBIT|DEBET|CR|KREDIT|CREDIT)\b", s, flags=re.IGNORECASE)

    if m_dir:
        token = m_dir.group(1).upper()
        if token in ("DB", "DR", "DEBIT", "DEBET", "D"):
            explicit_dir = "DB"
        elif token in ("CR", "KREDIT", "CREDIT", "C"):
            explicit_dir = "CR"

    num = clean_number(s)
    if explicit_dir == "DB" and num > 0:
        num = -num
    elif explicit_dir == "CR" and num < 0:
        num = abs(num)
    elif num < 0 and explicit_dir is None:
        explicit_dir = "DB"

    return num, explicit_dir


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
    if isinstance(val, dict):
        # Dukungan objek uang bersarang SNAP BI: {"value": "150000.00", "currency": "IDR"}
        for k in ("value", "amount", "nominal", "net", "gross"):
            if k in val:
                return clean_number(val[k])
        return 0.0

    s = str(val).strip()
    if not s or s.lower() in ("-", "--", "n/a", "null", "none", "nan", "nil", ""):
        return 0.0

    is_negative = False
    # Deteksi indikator DB / DR eksplisit pada string
    if re.search(r"(?:^|\s)(DB|DR|DEBIT|DEBET)(?:\s|$)", s, flags=re.IGNORECASE):
        # Jangan langsung jadikan negatif untuk clean_number umum kecuali tidak ada tanda lain,
        # namun hapus teksnya agar angka bersih.
        pass

    if (s.startswith("(") and s.endswith(")")) or s.endswith("-"):
        if not s.endswith((",-", ".-")):
            is_negative = True
            s = s.strip("()- ")

    # Bersihkan sufiks khusus Indonesia ',-' atau ',00-' atau '.-'
    s = re.sub(r",-\s*$", "", s)
    s = re.sub(r"\.-\s*$", "", s)

    # Hapus karakter non-angka selain titik, koma, dan minus
    s = re.sub(r"[^\d,\.\-]", "", s)
    if not s or s == "-":
        return 0.0

    if s.startswith("-"):
        is_negative = True
        s = s.lstrip("-")
    if s.endswith("-"):
        is_negative = True
        s = s.rstrip("-")

    # Analisis pemisah ribuan vs desimal
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            # Format Indonesia / Eropa: 1.500.000,50 (koma adalah desimal)
            s = s.replace(".", "").replace(",", ".")
        else:
            # Format Inggris / US: 1,500,000.50 (titik adalah desimal)
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
        if len(parts) > 2:
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


def clean_date(val: Any, default_year: int = 2026) -> str:
    """
    Mengonversi berbagai format tanggal ke format standar ISO YYYY-MM-DD:
    - ISO / Standar: '2026-08-15', '2026-08-15T14:30:00+07:00', '2026/08/15'
    - Format Indonesia / Eropa: '15/08/2026', '15-08-2026', '15.08.2026', '15/08/26'
    - Format KlikBCA Tanpa Tahun & Pending: '15/08', '15-08', 'PEND', 'PENDING'
    - Format Kompak 8-Digit: '20260815'
    - Nama Bulan (ID/EN): '15 Agu 2026', '15 Agustus 2026', 'Aug 15, 2026', '15-Aug-26', '15 Agu'
    - Angka Serial Tanggal Excel: 46249 -> '2026-08-15'
    - Unix Timestamp (detik / milidetik): 1786752000 -> '2026-08-15'
    """
    if val is None or pd.isna(val):
        return ""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")

    # Tangani angka numerik (Excel serial date atau Unix timestamp)
    if isinstance(val, (int, float)):
        num_val = float(val)
        if 30000 <= num_val <= 60000:
            base_excel = datetime(1899, 12, 30)
            return (base_excel + timedelta(days=int(num_val))).strftime("%Y-%m-%d")
        elif 1_000_000_000 <= num_val <= 2_500_000_000:
            return datetime.fromtimestamp(num_val, tz=timezone.utc).strftime("%Y-%m-%d")
        elif 1_000_000_000_000 <= num_val <= 2_500_000_000_000:
            return datetime.fromtimestamp(num_val / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")

    s = str(val).strip()
    if not s or s.lower() in ("-", "nan", "nat", "none", "null", ""):
        return ""

    # Tangani status tanggal 'PEND' / 'PENDING' pada KlikBCA
    if s.upper() in ("PEND", "PENDING", "HARI INI", "TODAY"):
        return f"{default_year}-08-15"

    # Tangani string digit murni (Excel serial 5 digit, YYYYMMDD 8 digit, atau Unix epoch 10/13 digit)
    if s.isdigit():
        if len(s) == 5 and 30000 <= int(s) <= 60000:
            base_excel = datetime(1899, 12, 30)
            return (base_excel + timedelta(days=int(s))).strftime("%Y-%m-%d")
        elif len(s) == 8:
            # Cek apakah YYYYMMDD (misal 20260815) atau DDMMYYYY (misal 15082026)
            if s.startswith(("19", "20")):
                return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
            elif s[4:].startswith(("19", "20")):
                return f"{s[4:8]}-{s[2:4]}-{s[:2]}"
        elif len(s) == 10:
            return datetime.fromtimestamp(int(s), tz=timezone.utc).strftime("%Y-%m-%d")
        elif len(s) == 13:
            return datetime.fromtimestamp(int(s) / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")

    # Potong bagian waktu ISO-8601 (misal '2026-08-15T10:20:30+07:00')
    if "T" in s and re.match(r"^\d{4}-\d{2}-\d{2}T", s):
        return s.split("T")[0]

    # Cek format dengan nama bulan teks (misal '15 Agu 2026', '15-Aug-26', 'Aug 15, 2026', '15 Agu')
    s_clean = re.sub(r"[,]", " ", s)
    tokens = [t for t in re.split(r"[\s\/\-\.]+", s_clean) if t]
    if len(tokens) >= 2:
        # Pola 1: DD <Bulan> [YYYY] (misal '15 Agustus 2026' atau '15 Agu')
        m1 = _MONTH_MAP.get(tokens[1].lower())
        if m1 and tokens[0].isdigit():
            day = tokens[0].zfill(2)
            year = str(default_year)
            if len(tokens) >= 3 and tokens[2].isdigit():
                year = tokens[2] if len(tokens[2]) == 4 else f"20{tokens[2]}"
            return f"{year}-{m1}-{day}"
        # Pola 2: <Bulan> DD [YYYY] (misal 'Aug 15 2026' atau 'Aug 15')
        m0 = _MONTH_MAP.get(tokens[0].lower())
        if m0 and tokens[1].isdigit():
            day = tokens[1].zfill(2)
            year = str(default_year)
            if len(tokens) >= 3 and tokens[2].isdigit():
                year = tokens[2] if len(tokens[2]) == 4 else f"20{tokens[2]}"
            return f"{year}-{m0}-{day}"

    # Ambil bagian tanggal saja jika ada jam 'YYYY-MM-DD HH:MM:SS'
    if " " in s:
        s = s.split(" ")[0]

    parts = re.split(r"[\/\-\.]", s)
    if len(parts) == 2 and all(p.isdigit() for p in parts):
        # Format KlikBCA DD/MM tanpa tahun (misal '15/08')
        d_part, m_part = parts[0].zfill(2), parts[1].zfill(2)
        if int(m_part) > 12 and int(d_part) <= 12:
            d_part, m_part = m_part, d_part
        return f"{default_year}-{m_part}-{d_part}"

    if len(parts) == 3 and all(p.isdigit() for p in parts):
        p1, p2, p3 = parts
        if len(p1) == 4:  # YYYY-MM-DD atau YYYY/MM/DD
            return f"{p1}-{p2.zfill(2)}-{p3.zfill(2)}"
        elif len(p3) == 4:  # DD-MM-YYYY atau MM-DD-YYYY
            if int(p2) > 12 and int(p1) <= 12:
                return f"{p3}-{p1.zfill(2)}-{p2.zfill(2)}"
            return f"{p3}-{p2.zfill(2)}-{p1.zfill(2)}"
        elif len(p3) == 2 and len(p1) <= 2 and len(p2) <= 2:  # DD/MM/YY
            year = f"20{p3}"
            if int(p2) > 12 and int(p1) <= 12:
                return f"{year}-{p1.zfill(2)}-{p2.zfill(2)}"
            return f"{year}-{p2.zfill(2)}-{p1.zfill(2)}"

    return s


def is_summary_or_noise_row(text_val: str) -> bool:
    """Mendeteksi apakah baris merupakan baris Saldo Awal/Akhir/Subtotal/Total yang harus dilewati."""
    up = (text_val or "").strip().upper()
    if not up or up in ("NAN", "NONE", "-"):
        return False
    return any(pat in up for pat in _SUMMARY_ROW_PATTERNS)


def extract_universal_bank_rows(
    df: pd.DataFrame,
    bank_code: str = "BANK_BCA",
    row_prefix: str = "BANK-ROW"
) -> List[BankStatementRow]:
    """
    Helper universal untuk mengekstrak baris mutasi bank dari DataFrame apa pun.
    Mendukung:
    - Kolom terpisah Debit & Kredit (Mandiri MCM, BNI Direct, BRI CMS, BSI, Buku Besar GL)
    - Kolom tunggal Jumlah/Mutasi + kolom Tipe (DB/CR)
    - Kolom tunggal Jumlah dengan indikator tertanam ('1.500.000,00 CR', '25.000 DB', '(25.000)')
    - Penggabungan otomatis kolom Nomor Referensi ke dalam keterangan agar pencocokan Batch akurat
    """
    if df is None or df.empty:
        return []

    cols_lower = {c: str(c).lower().strip() for c in df.columns}
    c_date = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("post date", "posting date", "value date", "tgl transaksi", "txn date", "tanggal", "tgl", "date", "waktu"))), df.columns[0])
    c_desc = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("keterangan", "uraian", "deskripsi", "description", "remark", "remarks", "narration", "narasi", "berita", "memo"))), df.columns[1] if len(df.columns) > 1 else df.columns[0])
    c_ref = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("referensi", "ref no", "reference", "no. ref", "kode transfer", "trx id")) and c != c_desc), None)

    # Deteksi kolom Debit & Kredit terpisah
    c_debit = next((c for c, cl in cols_lower.items() if any(k == cl or cl.startswith(k) or cl.endswith(k) for k in ("debit", "debet", "mutasi debet", "mutasi debit", "debit amount", "withdrawal", "uang keluar", "keluar"))), None)
    c_credit = next((c for c, cl in cols_lower.items() if any(k == cl or cl.startswith(k) or cl.endswith(k) for k in ("kredit", "credit", "mutasi kredit", "credit amount", "deposit", "uang masuk", "masuk"))), None)

    c_amt = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("jumlah", "amount", "nominal", "mutasi", "nilai", "total")) and c not in (c_debit, c_credit)), df.columns[-1])
    c_type = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("tipe", "type", "db/cr", "d/c", "jenis", "arus", "indikator"))), None)
    c_bal = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("saldo", "balance"))), None)

    rows: List[BankStatementRow] = []
    for idx, r in df.iterrows():
        desc = str(r.get(c_desc, "")).strip()
        if is_summary_or_noise_row(desc):
            continue

        date_str = clean_date(r.get(c_date, ""))
        if is_summary_or_noise_row(str(r.get(c_date, ""))):
            continue

        if c_ref and not pd.isna(r.get(c_ref)):
            ref_val = str(r.get(c_ref, "")).strip()
            if ref_val and ref_val.lower() not in ("nan", "none", "-") and ref_val not in desc:
                desc = f"{desc} [Ref: {ref_val}]".strip()

        bal = clean_number(r.get(c_bal)) if (c_bal and not pd.isna(r.get(c_bal))) else None

        amount = 0.0
        txn_type = "CR"

        if c_debit and c_credit:
            deb_val = abs(clean_number(r.get(c_debit, 0)))
            crd_val = abs(clean_number(r.get(c_credit, 0)))
            if crd_val > 0:
                amount, txn_type = crd_val, "CR"
            elif deb_val > 0:
                amount, txn_type = deb_val, "DB"
            else:
                continue
        else:
            raw_cell = r.get(c_amt, 0)
            amt_signed, embedded_dir = extract_amount_and_sign(raw_cell)
            if abs(amt_signed) <= 0:
                continue
            amount = abs(amt_signed)

            if c_type and not pd.isna(r.get(c_type)):
                t_str = str(r.get(c_type, "")).strip().upper()
                if any(t_str.startswith(p) for p in ("DB", "DEBIT", "DEBET", "DR", "D", "OUT", "KELUAR")):
                    txn_type = "DB"
                else:
                    txn_type = "CR"
            elif embedded_dir:
                txn_type = embedded_dir
            elif amt_signed < 0:
                txn_type = "DB"

        rows.append(BankStatementRow(
            row_id=f"{row_prefix}-{idx+1}",
            date=date_str or "2026-08-15",
            description=desc or f"Mutasi {bank_code} #{idx+1}",
            amount=amount,
            txn_type=txn_type,
            bank_code=bank_code,
            balance=bal,
            raw_data={str(k): str(v) for k, v in r.to_dict().items()}
        ))

    return rows


def _score_header_row(cells: List[Any]) -> int:
    """Menghitung skor kecocokan sebuah baris sebagai header tabel transaksi."""
    non_empty = [str(c).strip().lower() for c in cells if c is not None and not pd.isna(c) and str(c).strip()]
    if len(non_empty) < 2:
        return 0
    score = 0
    for cell in non_empty:
        if any(kw in cell for kw in _HEADER_KEYWORDS):
            score += 2
        if re.match(r"^[\d,\.\-\(\)\s]+$", cell) or re.match(r"^\d{4}-\d{2}-\d{2}$", cell):
            score -= 1
    return score


def _promote_header_row_if_needed(df: pd.DataFrame) -> pd.DataFrame:
    """
    Jika baris pertama DataFrame adalah metadata (misal 'Nomor Rekening: 123', 'Unnamed: 1'),
    cari baris header tabel yang sebenarnya pada 30 baris pertama dan jadikan sebagai kolom DataFrame.
    """
    if df is None or df.empty:
        return df

    current_cols = [str(c).strip() for c in df.columns]
    unnamed_count = sum(1 for c in current_cols if c.lower().startswith("unnamed:") or not c)
    current_score = _score_header_row(current_cols)

    if unnamed_count <= len(current_cols) // 3 and current_score >= 4:
        df.columns = current_cols
        return df.dropna(how="all").reset_index(drop=True)

    best_idx = -1
    best_score = current_score
    max_scan = min(len(df), 30)

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

    df = df.dropna(how="all").reset_index(drop=True)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _flatten_json_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Meratakan (flatten) 1 level objek JSON bersarang seperti format SNAP BI Open Banking."""
    flat: Dict[str, Any] = {}
    for k, v in rec.items():
        if isinstance(v, dict):
            if "value" in v and len(v) <= 3:
                flat[k] = v["value"]
                if "currency" in v:
                    flat[f"{k}_currency"] = v["currency"]
            else:
                for sub_k, sub_v in v.items():
                    flat[f"{k}_{sub_k}"] = sub_v
        else:
            flat[k] = v
    return flat


def _load_json_to_dataframe(raw_bytes: bytes) -> pd.DataFrame:
    """Membaca berkas JSON (Array, Nested API Object, SNAP BI, atau JSONL/NDJSON) menjadi DataFrame."""
    text = raw_bytes.decode("utf-8-sig", errors="replace").strip()
    if not text:
        return pd.DataFrame()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            rows = [_flatten_json_record(r) if isinstance(r, dict) else {"value": r} for r in parsed]
            return pd.DataFrame(rows)
        elif isinstance(parsed, dict):
            # Cek format Pandas orient='split' (memiliki key 'columns' dan 'data')
            if "columns" in parsed and "data" in parsed and isinstance(parsed["data"], list):
                return pd.DataFrame(parsed["data"], columns=parsed["columns"])
            # Cari key array yang menyimpan daftar transaksi
            for key in ("data", "transactions", "detailData", "records", "items", "orders", "settlements", "rows", "mutations", "results", "accountStatement"):
                if key in parsed and isinstance(parsed[key], list):
                    rows = [_flatten_json_record(r) if isinstance(r, dict) else {"value": r} for r in parsed[key]]
                    return pd.DataFrame(rows)
            # Cari sembarang key bernilai list of dicts
            for val in parsed.values():
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    rows = [_flatten_json_record(r) for r in val]
                    return pd.DataFrame(rows)
            return pd.DataFrame([_flatten_json_record(parsed)])
    except json.JSONDecodeError:
        records = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        records.append(_flatten_json_record(obj))
                except json.JSONDecodeError:
                    continue
        if records:
            return pd.DataFrame(records)
    return pd.DataFrame()


def _load_html_table_to_dataframe(raw_bytes: bytes) -> pd.DataFrame:
    """Membaca berkas .xls / .html yang berisi tabel HTML (<table><tr><td>...</td></tr></table>)."""
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    parser = _SimpleHTMLTableParser()
    try:
        parser.feed(text)
    except Exception:
        return pd.DataFrame()

    if not parser.tables:
        return pd.DataFrame()

    # Pilih tabel dengan jumlah baris terbanyak
    best_table = max(parser.tables, key=len)
    if not best_table:
        return pd.DataFrame()

    max_cols = max(len(r) for r in best_table)
    padded = [r + [""] * (max_cols - len(r)) for r in best_table]
    df = pd.DataFrame(padded[1:], columns=padded[0]) if len(padded) > 1 else pd.DataFrame(padded)
    return _promote_header_row_if_needed(df)


def _load_xml_to_dataframe(raw_bytes: bytes) -> pd.DataFrame:
    """Membaca berkas XML tabel generik maupun Microsoft XML Spreadsheet 2003 (<Row><Cell><Data>)."""
    text = raw_bytes.decode("utf-8-sig", errors="replace").strip()
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return pd.DataFrame()

    def _strip_ns(tag: str) -> str:
        return tag.split("}", 1)[-1] if "}" in tag else tag

    # 1. Cek apakah format Microsoft Excel XML Spreadsheet 2003 (<Workbook><Worksheet><Table><Row><Cell><Data>)
    spreadsheet_rows = []
    for elem in root.iter():
        if _strip_ns(elem.tag) == "Row":
            cells = []
            for sub in elem:
                if _strip_ns(sub.tag) == "Cell":
                    cell_text = "".join(sub.itertext()).strip()
                    cells.append(cell_text)
            if any(cells):
                spreadsheet_rows.append(cells)
    if len(spreadsheet_rows) >= 2:
        max_c = max(len(r) for r in spreadsheet_rows)
        padded = [r + [""] * (max_c - len(r)) for r in spreadsheet_rows]
        df_ss = pd.DataFrame(padded[1:], columns=padded[0])
        return _promote_header_row_if_needed(df_ss)

    # 2. XML Record List generik (<Records><Record>...</Record></Records>)
    rows = []
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


def _read_text_with_detected_delimiter(raw_bytes: bytes) -> pd.DataFrame:
    """
    Membaca berkas CSV/TSV/TXT dengan deteksi encoding otomatis, deteksi delimiter
    (',', ';', '\\t', '|', '^', '~', atau spasi ganda fixed-width), serta melewati baris metadata awal.
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

    # Deteksi delimiter terbaik dari 25 baris pertama
    sample_lines = lines[:25]
    candidate_delims = [",", ";", "\t", "|", "^", "~"]
    best_delim = None
    best_score = -1

    for d in candidate_delims:
        counts = [ln.count(d) for ln in sample_lines if ln.count(d) > 0]
        if counts:
            max_c = max(counts)
            score = len(counts) * min(max_c, 15)
            if score > best_score:
                best_score = score
                best_delim = d

    # Jika tidak ada karakter delimiter standar tetapi terdapat pemisah spasi ganda (2+ spaces Fixed-Width)
    if best_delim is None or best_score <= 1:
        multi_space_lines = [ln for ln in sample_lines if len(re.split(r"\s{2,}", ln.strip())) >= 3]
        if len(multi_space_lines) >= 2:
            rows_fwf = [re.split(r"\s{2,}", ln.strip()) for ln in lines]
            max_cols = max(len(r) for r in rows_fwf)
            padded = [r + [""] * (max_cols - len(r)) for r in rows_fwf if len(r) >= 2]
            if len(padded) >= 2:
                df_fwf = pd.DataFrame(padded[1:], columns=padded[0])
                return _promote_header_row_if_needed(df_fwf)
        best_delim = ","

    # Cari apakah ada baris metadata di atas baris header
    header_line_idx = 0
    best_hdr_score = -1
    for idx, ln in enumerate(lines[:30]):
        try:
            cells = next(csv.reader([ln], delimiter=best_delim))
        except Exception:
            cells = ln.split(best_delim)
        if len(cells) >= 2:
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
    Universal DataFrame Loader yang mampu membaca berbagai format fisik berkas:
    - Objek DataFrame langsung (Zero copy / Tanpa double-parsing)
    - Berkas terkompresi Gzip (.gz, .csv.gz, .json.gz)
    - Apache Parquet (.parquet, .pq) & Apache Feather (.feather, .arrow)
    - CSV/TSV/TXT dengan delimiter ',', ';', '\\t', '|', '^', '~', atau Fixed-Width (2+ spasi)
    - Excel (.xlsx, .xls, .ods) termasuk berkas .xls palsu yang berisi HTML <table> atau XML Spreadsheet 2003
    - JSON & NDJSON (.json, .jsonl, .ndjson) termasuk SNAP BI nested payload
    - XML (.xml) & HTML Table (.html, .htm)
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

    # 0. Dekompresi otomatis jika berkas dikompresi dengan Gzip (.gz / magic bytes 1f 8b)
    if fn_lower.endswith(".gz") or raw_bytes[:2] == b"\x1f\x8b":
        try:
            raw_bytes = gzip.decompress(raw_bytes)
            if fn_lower.endswith(".gz"):
                fn_lower = fn_lower[:-3]
        except Exception:
            pass

    head_strip = raw_bytes[:512].lstrip()
    head_lower = head_strip.lower()

    # 1. Deteksi Apache Parquet (.parquet, .pq, atau magic bytes PAR1)
    if fn_lower.endswith((".parquet", ".pq")) or raw_bytes[:4] == b"PAR1":
        try:
            df_pq = pd.read_parquet(io.BytesIO(raw_bytes))
            return _promote_header_row_if_needed(df_pq)
        except Exception:
            pass

    # 2. Deteksi Apache Feather / Arrow (.feather, .arrow, atau magic bytes FEA1)
    if fn_lower.endswith((".feather", ".arrow")) or raw_bytes[:4] == b"FEA1":
        try:
            df_ft = pd.read_feather(io.BytesIO(raw_bytes))
            return _promote_header_row_if_needed(df_ft)
        except Exception:
            pass

    # 3. Deteksi HTML Table (termasuk berkas .xls ekspor internet banking yang berisi <html> / <table>)
    if fn_lower.endswith((".html", ".htm")) or head_lower.startswith((b"<!doctype html", b"<html", b"<table")) or b"<table" in head_lower:
        df_html = _load_html_table_to_dataframe(raw_bytes)
        if not df_html.empty:
            return df_html

    # 4. Deteksi format JSON / JSONL
    if fn_lower.endswith((".json", ".jsonl", ".ndjson")) or head_strip.startswith((b"{", b"[")):
        df_json = _load_json_to_dataframe(raw_bytes)
        if not df_json.empty:
            df_json.columns = [str(c).strip() for c in df_json.columns]
            return df_json

    # 5. Deteksi format XML (termasuk SpreadsheetML 2003 .xls/.xml)
    if fn_lower.endswith((".xml", ".camt053")) or head_strip.startswith(b"<?xml") or b"<workbook" in head_lower:
        df_xml = _load_xml_to_dataframe(raw_bytes)
        if not df_xml.empty:
            df_xml.columns = [str(c).strip() for c in df_xml.columns]
            return df_xml

    # 6. Deteksi format Excel (.xlsx / .xls / .ods) atau ZIP PK header / BIFF8 OLE2 header
    if fn_lower.endswith((".xlsx", ".xls", ".ods")) or head_strip.startswith((b"PK\x03\x04", b"\xd0\xcf\x11\xe0")):
        try:
            df_excel = pd.read_excel(io.BytesIO(raw_bytes))
            return _promote_header_row_if_needed(df_excel)
        except Exception:
            return _read_text_with_detected_delimiter(raw_bytes)

    # 7. Default: CSV / TSV / TXT / Fixed-Width dengan auto-delimiter & header promotion
    return _read_text_with_detected_delimiter(raw_bytes)


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
