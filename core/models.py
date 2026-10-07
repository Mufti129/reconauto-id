"""
core/models.py
--------------
Model data terstandarisasi (Canonical Schema) untuk rekonsiliasi finansial multi-sumber.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

class SourceChannel(str, Enum):
    # --- 1. Bank Konvensional & Himbara ---
    BANK_BCA = "BANK_BCA"
    BANK_MANDIRI = "BANK_MANDIRI"
    BANK_BNI = "BANK_BNI"
    BANK_BRI = "BANK_BRI"
    BANK_CIMB = "BANK_CIMB"
    BANK_PERMATA = "BANK_PERMATA"
    BANK_DANAMON = "BANK_DANAMON"
    BANK_PANIN = "BANK_PANIN"
    BANK_OCBC = "BANK_OCBC"
    BANK_BTN = "BANK_BTN"

    # --- 2. Bank Syariah ---
    BANK_BSI = "BANK_BSI"
    BANK_MUAMALAT = "BANK_MUAMALAT"

    # --- 3. Bank Digital ---
    BANK_JAGO = "BANK_JAGO"
    BANK_JENIUS = "BANK_JENIUS"
    BANK_SEABANK = "BANK_SEABANK"
    BANK_BLU = "BANK_BLU"
    BANK_NEO = "BANK_NEO"

    # --- 4. Standar Perbankan Internasional ---
    BANK_SWIFT_MT940 = "BANK_SWIFT_MT940"
    BANK_CAMT053 = "BANK_CAMT053"

    # --- 5. Marketplace & Social Commerce ---
    MARKETPLACE_TIKTOK = "MARKETPLACE_TIKTOK"
    MARKETPLACE_SHOPEE = "MARKETPLACE_SHOPEE"
    MARKETPLACE_TOKOPEDIA = "MARKETPLACE_TOKOPEDIA"
    MARKETPLACE_LAZADA = "MARKETPLACE_LAZADA"
    MARKETPLACE_BLIBLI = "MARKETPLACE_BLIBLI"
    MARKETPLACE_BUKALAPAK = "MARKETPLACE_BUKALAPAK"

    # --- 6. Payment Gateway & FinTech ---
    PAYMENT_GATEWAY_DOKU = "PAYMENT_GATEWAY_DOKU"
    PAYMENT_GATEWAY_MIDTRANS = "PAYMENT_GATEWAY_MIDTRANS"
    PAYMENT_GATEWAY_XENDIT = "PAYMENT_GATEWAY_XENDIT"
    PAYMENT_GATEWAY_FASPAY = "PAYMENT_GATEWAY_FASPAY"
    PAYMENT_GATEWAY_DUITKU = "PAYMENT_GATEWAY_DUITKU"
    PAYMENT_GATEWAY_OY = "PAYMENT_GATEWAY_OY"
    PAYMENT_GATEWAY_ESPAY = "PAYMENT_GATEWAY_ESPAY"

    # --- 7. E-Wallet & QRIS Nasional ---
    EWALLET_GOPAY = "EWALLET_GOPAY"
    EWALLET_OVO = "EWALLET_OVO"
    EWALLET_DANA = "EWALLET_DANA"
    EWALLET_SHOPEEPAY = "EWALLET_SHOPEEPAY"
    EWALLET_LINKAJA = "EWALLET_LINKAJA"
    QRIS_NASIONAL = "QRIS_NASIONAL"

    # --- 8. Point of Sale (POS) Kasir Ritel ---
    POS_CASH = "POS_CASH"
    POS_JUBELIO = "POS_JUBELIO"
    POS_MOKA = "POS_MOKA"
    POS_PAWOON = "POS_PAWOON"
    POS_MAJOO = "POS_MAJOO"
    POS_ESB = "POS_ESB"

    # --- 9. Logistik Ekspedisi COD (3-Way) ---
    LOGISTICS_JNE_COD = "LOGISTICS_JNE_COD"
    LOGISTICS_SICEPAT_COD = "LOGISTICS_SICEPAT_COD"
    LOGISTICS_JNT_COD = "LOGISTICS_JNT_COD"
    LOGISTICS_ANTERAJA_COD = "LOGISTICS_ANTERAJA_COD"
    LOGISTICS_NINJA_COD = "LOGISTICS_NINJA_COD"
    LOGISTICS_IDEXPRESS_COD = "LOGISTICS_IDEXPRESS_COD"

    # --- 10. Biaya Iklan Digital (Ad Spend) ---
    ADS_META = "ADS_META"
    ADS_GOOGLE = "ADS_GOOGLE"
    ADS_TIKTOK = "ADS_TIKTOK"

    # --- 11. Pajak & Potongan Resmi ---
    TAX_PPH23 = "TAX_PPH23"
    TAX_PPN = "TAX_PPN"

    UNKNOWN = "UNKNOWN"

class ReconcileDirection(str, Enum):
    FORWARD = "FORWARD (Sumber -> Bank)"
    REVERSE = "REVERSE (Bank -> Sumber)"
    CROSS = "CROSS (Internal POS <-> Gateway / Cash)"

class DiscrepancySeverity(str, Enum):
    HIGH = "HIGH"       # Potensi uang hilang / tidak cair / overcharge
    MEDIUM = "MEDIUM"   # Selisih kasir / anomali pencatatan
    LOW = "LOW"         # Timing lag normal / biaya administrasi bank standar

@dataclass
class CanonicalTransaction:
    txn_id: str
    source_channel: SourceChannel
    date: str  # YYYY-MM-DD
    description: str
    gross_amount: float
    fee_amount: float
    net_amount: float
    batch_id: Optional[str] = None
    txn_type: str = "CREDIT"  # CREDIT or DEBIT
    raw_status: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BankStatementRow:
    row_id: str
    date: str  # YYYY-MM-DD
    description: str
    amount: float
    txn_type: str  # CR or DB
    bank_code: str = "BCA"
    account_number: Optional[str] = None
    branch: Optional[str] = None
    balance: Optional[float] = None
    matched: bool = False
    matched_with: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CodSettlementRow:
    awb_number: str
    courier_name: str
    order_id: str
    cod_amount: float
    courier_fee: float
    net_remitted: float
    settlement_date: str
    bank_ref_id: Optional[str] = None
    status: str = "PENDING"  # "CLEARED", "COD_UNREMITTED", "COD_SHORTAGE"
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BatchPayoutGroup:
    batch_id: str
    source_channel: SourceChannel
    settlement_date: str
    order_count: int
    gross_sum: float
    fee_sum: float
    net_sum: float
    bank_matched: bool = False
    bank_date: Optional[str] = None
    bank_amount: Optional[float] = None
    difference: float = 0.0
    status: str = "PENDING"  # MATCHED, TIMING_LAG, MISSING_PAYOUT
    notes: str = ""
    order_ids: List[str] = field(default_factory=list)

@dataclass
class DiscrepancyItem:
    id: str
    direction: ReconcileDirection
    channel: str
    reference_id: str
    date: str
    issue_type: str
    severity: DiscrepancySeverity
    expected_amount: float
    actual_amount: float
    discrepancy_amount: float
    probable_cause: str
    recommended_action: str
    metadata: Dict[str, Any] = field(default_factory=dict)
