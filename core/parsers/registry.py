"""
core/parsers/registry.py
------------------------
Registry dinamis untuk memuat, mendaftarkan, dan mendeteksi parser kanal sumber data secara otomatis.
"""

import os
import io
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union

from core.models import SourceChannel
from .base import BaseChannelParser, load_dataframe
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
)

class ParserRegistry:
    def __init__(self):
        self._parsers: Dict[str, BaseChannelParser] = {}
        self._register_builtins()

    def _register_builtins(self):
        # 1. Banks (Himbara & Swasta)
        self.register(BcaParser())
        self.register(MandiriParser())
        self.register(BniParser())
        self.register(BriParser())
        self.register(CimbParser())
        self.register(PermataParser())
        self.register(BsiParser())
        self.register(Mt940Parser())

        # 2. Marketplaces
        self.register(TiktokShopParser())
        self.register(ShopeeParser())
        self.register(TokopediaParser())

        # 3. Payment Gateways & E-Wallet
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
        
        # Tambahkan katalog sumber data ekosistem Indonesia lainnya yang didukung oleh platform
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

    def detect_and_parse(self, source: Union[str, io.BytesIO, bytes], filename: str = "") -> Tuple[SourceChannel, List[Any]]:
        """
        Mendeteksi parser yang paling cocok secara otomatis, kemudian mengeksekusi parsing.
        """
        # Cek format file biner khusus (misal PDF)
        fn_lower = filename.lower()
        if fn_lower.endswith(".pdf"):
            bca = self.get("BANK_BCA")
            if bca and bca.detect_format(filename=filename):
                return bca.parse(source, filename)

        if fn_lower.endswith(".sta") or fn_lower.endswith(".mt940"):
            mt = self.get("BANK_MT940")
            if mt:
                return mt.parse(source, filename)

        # Muat DataFrame untuk pemeriksaan tanda tangan kolom
        try:
            # Jika source adalah BytesIO, gandakan agar bisa dibaca ulang jika perlu
            if isinstance(source, bytes):
                src_copy = io.BytesIO(source)
            elif hasattr(source, "read"):
                content = source.read()
                src_copy = io.BytesIO(content) if isinstance(content, bytes) else io.StringIO(str(content))
                if hasattr(source, "seek"):
                    source.seek(0)
            elif isinstance(source, str) and os.path.exists(source):
                with open(source, "rb") as f:
                    src_copy = io.BytesIO(f.read())
            else:
                src_copy = source

            df = load_dataframe(src_copy, filename)
        except Exception:
            df = None

        # Prioritas 1: Cek nama file spesifik
        for p in self._parsers.values():
            if p.detect_format(df=df, filename=filename):
                if hasattr(src_copy, "seek"):
                    src_copy.seek(0)
                return p.parse(src_copy, filename)

        # Fallback jika tidak terdeteksi
        return SourceChannel.UNKNOWN, []

# Singleton registry default
default_registry = ParserRegistry()
