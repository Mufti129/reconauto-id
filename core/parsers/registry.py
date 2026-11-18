"""
core/parsers/registry.py
------------------------
Registry dinamis untuk memuat, mendaftarkan, dan mendeteksi parser kanal sumber data secara otomatis.
Mendukung berbagai format input:
- CSV (koma ',', titik koma ';', tab '\\t', pipe '|') & TSV/TXT
- Excel (.xlsx, .xls) Single-Sheet & Multi-Sheet Workbook
- PDF e-Statement Perbankan (.pdf)
- Standar Perbankan SWIFT MT940 (.sta, .mt940, .swift)
- Standar Perbankan ISO 20022 CAMT.053 XML & OFX/QFX (.xml, .camt053, .ofx, .qfx)
- JSON Array, Nested API Payload & JSON Lines (.json, .jsonl, .ndjson)
- Bundel Arsip ZIP Multi-Berkas (.zip)
- Universal Smart Adaptive Fallback untuk skema ERP / Kustom
"""

import os
import io
import zipfile
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union

from core.models import SourceChannel
from .base import BaseChannelParser, load_dataframe, _promote_header_row_if_needed
from .bank.bca_parser import BcaParser
from .bank.mandiri_parser import MandiriParser
from .bank.bni_parser import BniParser
from .bank.bri_parser import BriParser
from .bank.mt940_parser import Mt940Parser
from .marketplace.tiktok_parser import TiktokShopParser
from .marketplace.shopee_parser import ShopeeParser
from .payment_gateway.doku_parser import DokuParser
from .pos.pos_cash_parser import PosCashParser
from .pos.jubelio_parser import JubelioPosParser
from .logistics.jne_cod_parser import JneCodParser
from .logistics.sicepat_cod_parser import SicepatCodParser
from .extended_parsers import (
    MidtransParser,
    XenditParser,
    TokopediaParser,
    CimbParser,
    JntCodParser,
    MokaPosParser,
    QrisNationalParser,
    PermataParser,
    BsiParser,
    Camt053XmlParser,
    LazadaParser,
    UniversalSmartParser,
)

MAX_ZIP_EXTRACTED_BYTES = 50 * 1024 * 1024  # 50 MB proteksi Zip Bomb
MAX_ZIP_FILES = 40


class ParserRegistry:
    def __init__(self):
        self._parsers: Dict[str, BaseChannelParser] = {}
        self._universal_parser = UniversalSmartParser()
        self._register_builtins()

    def _register_builtins(self):
        # 1. Banks (Himbara, Swasta, Syariah & Standar Internasional)
        self.register(BcaParser())
        self.register(MandiriParser())
        self.register(BniParser())
        self.register(BriParser())
        self.register(CimbParser())
        self.register(PermataParser())
        self.register(BsiParser())
        self.register(Mt940Parser())
        self.register(Camt053XmlParser())

        # 2. Marketplaces
        self.register(TiktokShopParser())
        self.register(ShopeeParser())
        self.register(TokopediaParser())
        self.register(LazadaParser())

        # 3. Payment Gateways & E-Wallet / QRIS
        self.register(DokuParser())
        self.register(MidtransParser())
        self.register(XenditParser())
        self.register(QrisNationalParser())

        # 4. Point of Sale (POS)
        self.register(PosCashParser())
        self.register(JubelioPosParser())
        self.register(MokaPosParser())

        # 5. Logistics / COD
        self.register(JneCodParser())
        self.register(SicepatCodParser())
        self.register(JntCodParser())

    def register(self, parser: BaseChannelParser):
        """Mendaftarkan instance adapter parser baru ke registry."""
        self._parsers[parser.channel_id] = parser

    def get(self, channel_id: str) -> Optional[BaseChannelParser]:
        return self._parsers.get(channel_id)

    def list_supported_formats(self) -> List[Dict[str, Any]]:
        """Mengembalikan daftar spesifikasi format fisik berkas yang didukung oleh sistem."""
        return [
            {"format_id": "CSV_DELIMITED", "extensions": [".csv", ".tsv", ".txt"], "description": "Delimited Text (Auto-detect koma ',', titik koma ';', tab '\\t', pipe '|' & skip baris metadata)"},
            {"format_id": "EXCEL_WORKBOOK", "extensions": [".xlsx", ".xls"], "description": "Microsoft Excel Workbook (Single-Sheet, Multi-Sheet Konsolidasi & HTML-based .xls)"},
            {"format_id": "PDF_ESTATEMENT", "extensions": [".pdf"], "description": "Dokumen e-Statement Rekening Koran Bank Digital (Ekstraksi Tabel Otomatis)"},
            {"format_id": "SWIFT_MT940", "extensions": [".sta", ".mt940", ".swift"], "description": "Standar Perbankan Internasional SWIFT MT940 (Tag :20:, :61:, :86:)"},
            {"format_id": "ISO20022_CAMT053_OFX", "extensions": [".xml", ".camt053", ".ofx", ".qfx"], "description": "Standar ISO 20022 CAMT.053 XML (<BkToCstmrStmt>) & Open Financial Exchange (OFX/QFX)"},
            {"format_id": "JSON_API_PAYLOAD", "extensions": [".json", ".jsonl", ".ndjson"], "description": "JSON Array, Nested Webhook/API Payload (Open Banking SNAP BI / PG), & JSON Lines"},
            {"format_id": "ZIP_BUNDLE", "extensions": [".zip"], "description": "Arsip Bundel Multi-Berkas (Ekstraksi & klasifikasi otomatis seluruh file di dalam ZIP)"},
            {"format_id": "UNIVERSAL_ADAPTIVE", "extensions": ["*"], "description": "Universal Smart Heuristic Mapper untuk ekspor ERP/Akuntansi kustom (SAP, Odoo, Accurate, Jurnal)"},
        ]

    def list_channels(self) -> List[Dict[str, Any]]:
        """Mengembalikan metadata seluruh kanal yang terdaftar di registry dengan kategori terstruktur."""
        registered = [
            {
                "channel_id": p.channel_id,
                "channel_name": p.channel_name,
                "channel_type": p.classify_channel_type(),
                "matching_strategy": p.get_matching_strategy(),
                "is_active": True
            }
            for p in self._parsers.values()
        ]

        catalog_extensions = [
            {"channel_id": "BANK_PERMATA", "channel_name": "Bank Permata (Permatae-Business / PeB)", "channel_type": "BANK", "matching_strategy": "REFERENCE_BASED", "is_active": True},
            {"channel_id": "BANK_DANAMON", "channel_name": "Bank Danamon (DCC Cash Connect)", "channel_type": "BANK", "matching_strategy": "REFERENCE_BASED", "is_active": True},
            {"channel_id": "BANK_BSI", "channel_name": "Bank Syariah Indonesia (BSI Cash Management)", "channel_type": "BANK", "matching_strategy": "REFERENCE_BASED", "is_active": True},
            {"channel_id": "BANK_JAGO", "channel_name": "Bank Jago Bisnis (Digital Statement)", "channel_type": "BANK", "matching_strategy": "REFERENCE_BASED", "is_active": True},
            {"channel_id": "BANK_JENIUS", "channel_name": "Jenius BTPN (e-Statement Bisnis)", "channel_type": "BANK", "matching_strategy": "REFERENCE_BASED", "is_active": True},
            {"channel_id": "BANK_SEABANK", "channel_name": "SeaBank Indonesia (Rekening Merchant)", "channel_type": "BANK", "matching_strategy": "REFERENCE_BASED", "is_active": True},
            {"channel_id": "MARKETPLACE_LAZADA", "channel_name": "Lazada Seller Center (Account Statement)", "channel_type": "MARKETPLACE", "matching_strategy": "BATCH_BASED", "is_active": True},
            {"channel_id": "MARKETPLACE_BLIBLI", "channel_name": "Blibli Merchant Settlement", "channel_type": "MARKETPLACE", "matching_strategy": "BATCH_BASED", "is_active": True},
            {"channel_id": "PAYMENT_GATEWAY_FASPAY", "channel_name": "Faspay Payment Gateway", "channel_type": "PAYMENT_GATEWAY", "matching_strategy": "REFERENCE_BASED", "is_active": True},
            {"channel_id": "PAYMENT_GATEWAY_DUITKU", "channel_name": "Duitku Payment Gateway", "channel_type": "PAYMENT_GATEWAY", "matching_strategy": "REFERENCE_BASED", "is_active": True},
            {"channel_id": "QRIS_NASIONAL", "channel_name": "QRIS Nasional (NMID Merchant Aggregator)", "channel_type": "EWALLET_QRIS", "matching_strategy": "REFERENCE_BASED", "is_active": True},
            {"channel_id": "EWALLET_GOPAY", "channel_name": "GoPay / GoBiz Merchant Settlement", "channel_type": "EWALLET_QRIS", "matching_strategy": "REFERENCE_BASED", "is_active": True},
            {"channel_id": "EWALLET_OVO", "channel_name": "OVO Merchant Settlement Report", "channel_type": "EWALLET_QRIS", "matching_strategy": "REFERENCE_BASED", "is_active": True},
            {"channel_id": "EWALLET_DANA", "channel_name": "DANA Bisnis Merchant Portal", "channel_type": "EWALLET_QRIS", "matching_strategy": "REFERENCE_BASED", "is_active": True},
            {"channel_id": "POS_MOKA", "channel_name": "Moka POS (Laporan Kasir & Settlement)", "channel_type": "POS", "matching_strategy": "CROSS_VALIDATION", "is_active": True},
            {"channel_id": "POS_PAWOON", "channel_name": "Pawoon POS Kasir Ritel", "channel_type": "POS", "matching_strategy": "CROSS_VALIDATION", "is_active": True},
            {"channel_id": "POS_MAJOO", "channel_name": "Majoo POS Rekonsiliasi Kas Harian", "channel_type": "POS", "matching_strategy": "CROSS_VALIDATION", "is_active": True},
            {"channel_id": "LOGISTICS_ANTERAJA_COD", "channel_name": "Anteraja COD Remittance", "channel_type": "LOGISTICS", "matching_strategy": "THREE_WAY_COD", "is_active": True},
            {"channel_id": "LOGISTICS_NINJA_COD", "channel_name": "Ninja Xpress COD Settlement", "channel_type": "LOGISTICS", "matching_strategy": "THREE_WAY_COD", "is_active": True},
            {"channel_id": "ADS_META", "channel_name": "Meta Ads (Facebook & Instagram Invoice)", "channel_type": "ADS_TAX", "matching_strategy": "TAX_EXPENSE", "is_active": True},
            {"channel_id": "ADS_GOOGLE", "channel_name": "Google Ads Tax Statement (IDR)", "channel_type": "ADS_TAX", "matching_strategy": "TAX_EXPENSE", "is_active": True},
            {"channel_id": "TAX_PPH23", "channel_name": "Bukti Potong PPh 23 Unifikasi (2% Platform)", "channel_type": "ADS_TAX", "matching_strategy": "TAX_EXPENSE", "is_active": True},
        ]
        registered_ids = {r["channel_id"] for r in registered}
        filtered_extensions = [c for c in catalog_extensions if c["channel_id"] not in registered_ids]

        return registered + filtered_extensions

    @staticmethod
    def _to_bytes(source: Union[str, io.BytesIO, bytes, pd.DataFrame]) -> Optional[bytes]:
        if isinstance(source, pd.DataFrame):
            return None
        if isinstance(source, bytes):
            return source
        if hasattr(source, "read"):
            if hasattr(source, "seek"):
                source.seek(0)
            content = source.read()
            if hasattr(source, "seek"):
                source.seek(0)
            return content if isinstance(content, bytes) else str(content).encode("utf-8")
        if isinstance(source, str):
            if os.path.exists(source):
                with open(source, "rb") as f:
                    return f.read()
            return source.encode("utf-8")
        return None

    def detect_and_parse(
        self,
        source: Union[str, io.BytesIO, bytes, pd.DataFrame],
        filename: str = ""
    ) -> Tuple[SourceChannel, List[Any]]:
        """
        Mendeteksi parser yang paling cocok secara otomatis dan mengeksekusi parsing.
        Dilengkapi fallback ke UniversalSmartParser jika format kustom.
        """
        fn_lower = (filename or "").lower().strip()
        raw_bytes = self._to_bytes(source)

        # 1. Cek format PDF e-Statement Bank
        if fn_lower.endswith(".pdf") or (raw_bytes and raw_bytes[:5] == b"%PDF-"):
            bca = self.get("BANK_BCA")
            if bca:
                return bca.parse(raw_bytes or source, filename)

        # Siapkan pratinjau teks mentah untuk deteksi format berbasis tag (MT940, CAMT.053, OFX)
        raw_text_preview = ""
        if raw_bytes and not raw_bytes[:4].startswith(b"PK\x03\x04"):
            raw_text_preview = raw_bytes[:4096].decode("utf-8-sig", errors="ignore")

        # 2. Cek format SWIFT MT940 (.sta, .mt940, .swift, atau teks dengan tag :20: & :61:)
        mt = self.get("BANK_MT940")
        if mt and mt.detect_format(filename=filename, raw_text=raw_text_preview):
            return mt.parse(raw_bytes or source, filename)

        # 3. Cek format ISO 20022 CAMT.053 XML & OFX/QFX
        camt = self.get("BANK_CAMT053")
        if camt and camt.detect_format(filename=filename, raw_text=raw_text_preview):
            ch, rows = camt.parse(raw_bytes or source, filename)
            if rows:
                return ch, rows

        # 4. Muat DataFrame satu kali (Zero double-parsing) untuk CSV/TSV/Excel/JSON/XML
        try:
            df = source if isinstance(source, pd.DataFrame) else load_dataframe(raw_bytes if raw_bytes is not None else source, filename)
        except Exception:
            df = None

        # 5. Prioritas 1: Cek parser spesifik terdaftar
        for p in self._parsers.values():
            if p.channel_id in ("BANK_MT940", "BANK_CAMT053"):
                continue
            try:
                if p.detect_format(df=df, filename=filename, raw_text=raw_text_preview):
                    target_input = df if (df is not None and not df.empty) else (raw_bytes or source)
                    ch, records = p.parse(target_input, filename)
                    if records:
                        return ch, records
            except Exception:
                continue

        # 6. Fallback Cerdas: Universal Smart Adaptive Mapper untuk skema kustom / ERP / Delimiter khusus
        if df is not None and not df.empty:
            try:
                ch, records = self._universal_parser.parse(df, filename)
                if records:
                    return ch, records
            except Exception:
                pass

        return SourceChannel.UNKNOWN, []

    def parse_multi_source(
        self,
        source: Union[str, io.BytesIO, bytes, pd.DataFrame],
        filename: str = ""
    ) -> List[Tuple[SourceChannel, List[Any], str]]:
        """
        Mampu mengekstrak dan mem-parsing:
        - Berkas tunggal (CSV, TSV, TXT, PDF, JSON, XML, MT940, OFX, CAMT.053)
        - Arsip bundel .zip yang berisi banyak berkas sekaligus
        - Workbook Excel .xlsx yang memiliki banyak sheet (Multi-Sheet)
        Mengembalikan list of (SourceChannel, records, source_label).
        """
        fn_lower = (filename or "").lower().strip()
        raw_bytes = self._to_bytes(source)
        results: List[Tuple[SourceChannel, List[Any], str]] = []

        # 1. Jika berkas adalah arsip .zip (dan bukan .xlsx/.xls)
        if fn_lower.endswith(".zip") and raw_bytes:
            try:
                with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as zf:
                    extracted_total = 0
                    file_count = 0
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        inner_name = os.path.basename(info.filename)
                        if not inner_name or inner_name.startswith((".", "__")):
                            continue
                        file_count += 1
                        if file_count > MAX_ZIP_FILES:
                            break
                        extracted_total += info.file_size
                        if extracted_total > MAX_ZIP_EXTRACTED_BYTES:
                            break
                        inner_bytes = zf.read(info.filename)
                        sub_results = self.parse_multi_source(inner_bytes, filename=inner_name)
                        results.extend(sub_results)
                if results:
                    return results
            except Exception:
                pass

        # 2. Jika berkas adalah Excel .xlsx dengan banyak sheet (Multi-Sheet Workbook)
        if fn_lower.endswith((".xlsx", ".xls")) and raw_bytes and raw_bytes[:4] == b"PK\x03\x04":
            try:
                excel_file = pd.ExcelFile(io.BytesIO(raw_bytes))
                if len(excel_file.sheet_names) > 1:
                    for sheet_name in excel_file.sheet_names:
                        try:
                            raw_sheet_df = excel_file.parse(sheet_name)
                            sheet_df = _promote_header_row_if_needed(raw_sheet_df)
                            if sheet_df is None or sheet_df.empty:
                                continue
                            virtual_name = f"{filename} [{sheet_name}]"
                            ch, data = self.detect_and_parse(sheet_df, filename=f"{filename}_{sheet_name}")
                            if ch != SourceChannel.UNKNOWN and data:
                                results.append((ch, data, virtual_name))
                        except Exception:
                            continue
                    if results:
                        return results
            except Exception:
                pass

        # 3. Default: Berkas tunggal
        ch, data = self.detect_and_parse(raw_bytes if raw_bytes is not None else source, filename=filename)
        if ch != SourceChannel.UNKNOWN and data:
            results.append((ch, data, filename or ch.value))
        return results


# Singleton registry default
default_registry = ParserRegistry()
