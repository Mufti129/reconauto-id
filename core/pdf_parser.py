"""
core/pdf_parser.py
------------------
Parser mutasi rekening koran bank berformat PDF (BCA KlikBCA Bisnis & standard Indonesian e-statements).
Menggunakan pypdf untuk mengekstrak baris tabel transaksi secara otomatis.
"""

import io
import re
from typing import List, Union
from pypdf import PdfReader
from .models import BankStatementRow
from .parser import clean_number, clean_date

def parse_bank_pdf(source: Union[bytes, io.BytesIO, str]) -> List[BankStatementRow]:
    """
    Mengekstrak baris mutasi bank dari file PDF rekening koran.
    """
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    elif isinstance(source, str):
        with open(source, "rb") as f:
            source = io.BytesIO(f.read())
            
    reader = PdfReader(source)
    all_lines = []
    
    for page in reader.pages:
        text = page.extract_text()
        if text:
            for line in text.splitlines():
                line_str = line.strip()
                if line_str:
                    all_lines.append(line_str)
                    
    return _extract_bca_rows(all_lines)

def _extract_bca_rows(lines: List[str]) -> List[BankStatementRow]:
    """
    Mengenali dan membedah baris-baris transaksi mutasi bank BCA dari kumpulan teks PDF.
    Format umum:
    TANGGAL | KETERANGAN | CABANG | JUMLAH | TIPE (CR/DB) | SALDO
    """
    rows = []
    row_idx = 1
    
    # Regex pola tanggal di awal baris atau sebagai baris tersendiri: YYYY-MM-DD atau DD/MM/YYYY atau DD-MM-YYYY
    date_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4})")
    
    # Filter header dokumen
    cleaned_lines = []
    for line in lines:
        upper = line.upper()
        if any(h in upper for h in ["REKENING KORAN", "NO REKENING", "NO. REKENING", "PERIODE", "TANGGAL KETERANGAN", "HALAMAN"]):
            continue
        cleaned_lines.append(line)
        
    # Kelompokkan teks per transaksi berdasarkan kemunculan tanggal
    blocks: List[List[str]] = []
    curr_block: List[str] = []
    
    for line in cleaned_lines:
        if date_pattern.match(line):
            if curr_block:
                blocks.append(curr_block)
            curr_block = [line]
        else:
            if curr_block:
                curr_block.append(line)
    if curr_block:
        blocks.append(curr_block)
        
    for block in blocks:
        full_text = " ".join(block)
        m = date_pattern.match(block[0])
        if not m:
            continue
            
        raw_date = m.group(1)
        iso_date = clean_date(raw_date)
        
        # Abaikan baris saldo awal
        if "SALDO AWAL" in full_text.upper():
            continue
            
        # Tentukan tipe DB atau CR
        txn_type = "CR"
        if any(t.strip().upper() in ["DB", "DEBIT", "DEBET"] for t in block):
            txn_type = "DB"
        elif any(t.strip().upper() in ["CR", "KREDIT"] for t in block):
            txn_type = "CR"
            
        # Jika format per-sel (seperti tabel ReportLab):
        # block = [date, desc_1, desc_2..., cab, jumlah, tipe, saldo]
        if len(block) >= 5 and block[-2].upper() in ["CR", "DB", "KREDIT", "DEBIT"]:
            desc = " ".join(block[1:-4]).strip() if len(block) > 5 else block[1]
            amt = clean_number(block[-3])
            bal = clean_number(block[-1])
        else:
            # Format teks bebas / spasi dalam 1 baris
            # Ekstrak semua token
            tokens = full_text[len(raw_date):].split()
            numeric_tokens = []
            desc_tokens = []
            
            for t in tokens:
                cleaned = t.replace(".", "").replace(",", "").replace("-", "").strip()
                if cleaned.isdigit() and len(cleaned) >= 2:
                    numeric_tokens.append(t)
                elif t.upper() not in ["CR", "DB", "KREDIT", "DEBET"]:
                    desc_tokens.append(t)
                    
            desc = " ".join(desc_tokens).strip()
            amt = 0.0
            bal = None
            if len(numeric_tokens) >= 2:
                amt = clean_number(numeric_tokens[-2])
                bal = clean_number(numeric_tokens[-1])
            elif len(numeric_tokens) == 1:
                amt = clean_number(numeric_tokens[0])
                
        if amt > 0:
            rows.append(BankStatementRow(
                row_id=f"BCA-PDF-{row_idx}",
                date=iso_date,
                description=desc,
                amount=amt,
                txn_type=txn_type,
                balance=bal,
                raw_data={"raw_block": block}
            ))
            row_idx += 1
            
    return rows
