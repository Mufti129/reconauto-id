"""
core/db.py
----------
Modul persistensi SQLite untuk menyimpan riwayat rekonsiliasi finansial
dan melacak status penyelesaian rolling antar-periode (Rolling Reconciliation).
"""

import os
import json
import uuid
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rekonsile.db")

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def init_db(db_path: Optional[str] = None):
    """Menginisialisasi seluruh tabel relasional rekonsiliasi jika belum ada."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 1. Tabel Riwayat Sesi Rekonsiliasi
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reconciliation_runs (
        id TEXT PRIMARY KEY,
        run_date TEXT NOT NULL,
        period_start TEXT,
        period_end TEXT,
        source_description TEXT,
        total_gross REAL DEFAULT 0,
        total_fees REAL DEFAULT 0,
        total_net REAL DEFAULT 0,
        total_bank_cleared REAL DEFAULT 0,
        bank_total_credits REAL DEFAULT 0,
        bank_total_debits REAL DEFAULT 0,
        in_transit_amount REAL DEFAULT 0,
        missing_payout_amount REAL DEFAULT 0,
        proof_difference REAL DEFAULT 0,
        is_balanced INTEGER DEFAULT 1,
        match_rate_pct REAL DEFAULT 0,
        transactions_count INTEGER DEFAULT 0,
        batches_count INTEGER DEFAULT 0,
        exceptions_count INTEGER DEFAULT 0,
        raw_summary_json TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # 2. Tabel Batch Payout (Kumpulan Order ke Bank)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stored_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        batch_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        settlement_date TEXT,
        order_count INTEGER DEFAULT 0,
        gross_sum REAL DEFAULT 0,
        fee_sum REAL DEFAULT 0,
        net_sum REAL DEFAULT 0,
        bank_matched INTEGER DEFAULT 0,
        bank_date TEXT,
        bank_amount REAL DEFAULT 0,
        difference REAL DEFAULT 0,
        status TEXT NOT NULL,
        notes TEXT,
        is_open_in_transit INTEGER DEFAULT 0,
        resolved_in_run_id TEXT,
        resolved_at TEXT,
        FOREIGN KEY (run_id) REFERENCES reconciliation_runs(id) ON DELETE CASCADE
    )
    """)

    # 3. Tabel Riwayat Transaksi Kanonikal (Pesanan/Penjualan Kasir)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stored_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        txn_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        date TEXT,
        description TEXT,
        gross_amount REAL DEFAULT 0,
        fee_amount REAL DEFAULT 0,
        net_amount REAL DEFAULT 0,
        batch_id TEXT,
        raw_status TEXT,
        metadata_json TEXT,
        FOREIGN KEY (run_id) REFERENCES reconciliation_runs(id) ON DELETE CASCADE
    )
    """)

    # 4. Tabel Mutasi Bank
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stored_bank_rows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        row_id TEXT NOT NULL,
        date TEXT,
        description TEXT,
        amount REAL DEFAULT 0,
        txn_type TEXT NOT NULL,
        balance REAL,
        matched INTEGER DEFAULT 0,
        matched_batch_id TEXT,
        FOREIGN KEY (run_id) REFERENCES reconciliation_runs(id) ON DELETE CASCADE
    )
    """)

    # 5. Tabel Anomali & Temuan (Discrepancies)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stored_discrepancies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        disc_id TEXT NOT NULL,
        direction TEXT NOT NULL,
        channel TEXT,
        reference_id TEXT,
        date TEXT,
        issue_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        expected_amount REAL DEFAULT 0,
        actual_amount REAL DEFAULT 0,
        discrepancy_amount REAL DEFAULT 0,
        probable_cause TEXT,
        recommended_action TEXT,
        resolution_status TEXT DEFAULT 'OPEN',
        FOREIGN KEY (run_id) REFERENCES reconciliation_runs(id) ON DELETE CASCADE
    )
    """)

    # 6. Tabel Multi-Entity / Workspaces
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workspaces (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        tax_id TEXT,
        default_bank_name TEXT,
        default_account_num TEXT,
        coa_mapping_json TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # 7. Tabel Log Sinkronisasi API Akuntansi (Mekari Jurnal, Accurate Online, Xero)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounting_sync_logs (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        journal_ref_number TEXT NOT NULL,
        entry_count INTEGER DEFAULT 0,
        total_debit REAL DEFAULT 0,
        total_credit REAL DEFAULT 0,
        payload_json TEXT,
        response_json TEXT,
        status TEXT DEFAULT 'SUCCESS',
        synced_at TEXT NOT NULL,
        FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
    )
    """)

    # 8. Tabel Pengguna Akun SaaS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        store_name TEXT,
        plan TEXT DEFAULT 'FREE_TRIAL',
        trial_runs_used INTEGER DEFAULT 0,
        max_trial_runs INTEGER DEFAULT 2,
        created_at TEXT NOT NULL
    )
    """)

    # 9. Tabel Sesi Login Pengguna
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
        token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # 10. Tabel Registry Sumber Data (Fase 3A)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS source_channels (
        channel_id TEXT PRIMARY KEY,
        channel_name TEXT NOT NULL,
        channel_type TEXT NOT NULL,
        matching_strategy TEXT NOT NULL,
        parser_class TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """)

    # 11. Tabel Settlement COD Kurir (Fase 3A - 3-Way Matching)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stored_cod_settlements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        awb_number TEXT NOT NULL,
        courier_name TEXT NOT NULL,
        order_id TEXT NOT NULL,
        cod_amount REAL DEFAULT 0,
        courier_fee REAL DEFAULT 0,
        net_remitted REAL DEFAULT 0,
        settlement_date TEXT,
        bank_ref_id TEXT,
        status TEXT NOT NULL DEFAULT 'PENDING',
        metadata_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES reconciliation_runs(id) ON DELETE CASCADE
    )
    """)

    # Migration: pastikan workspace_id & user_id ada di reconciliation_runs
    cursor.execute("PRAGMA table_info(reconciliation_runs)")
    col_names = [col[1] for col in cursor.fetchall()]
    if "workspace_id" not in col_names:
        cursor.execute("ALTER TABLE reconciliation_runs ADD COLUMN workspace_id TEXT DEFAULT 'ws-default'")
    if "user_id" not in col_names:
        cursor.execute("ALTER TABLE reconciliation_runs ADD COLUMN user_id TEXT DEFAULT 'user-demo'")

    # Migration: pastikan bank_code & account_number ada di stored_bank_rows
    cursor.execute("PRAGMA table_info(stored_bank_rows)")
    bank_cols = [col[1] for col in cursor.fetchall()]
    if "bank_code" not in bank_cols:
        cursor.execute("ALTER TABLE stored_bank_rows ADD COLUMN bank_code TEXT DEFAULT 'BCA'")
    if "account_number" not in bank_cols:
        cursor.execute("ALTER TABLE stored_bank_rows ADD COLUMN account_number TEXT")

    # Migration: pastikan channel_id ada di stored_discrepancies
    cursor.execute("PRAGMA table_info(stored_discrepancies)")
    disc_cols = [col[1] for col in cursor.fetchall()]
    if "channel_id" not in disc_cols:
        cursor.execute("ALTER TABLE stored_discrepancies ADD COLUMN channel_id TEXT")

    # Indeks performa pencarian
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_batches_open ON stored_batches (is_open_in_transit, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_batches_ref ON stored_batches (batch_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_date ON reconciliation_runs (run_date DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_ws ON accounting_sync_logs (workspace_id, synced_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions (token)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cod_run ON stored_cod_settlements (run_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cod_awb ON stored_cod_settlements (awb_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cod_status ON stored_cod_settlements (status)")

    # Seed Registry Sumber Data Bawaan jika kosong
    cursor.execute("SELECT COUNT(*) FROM source_channels")
    if cursor.fetchone()[0] == 0:
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        builtin_sources = [
            ("BANK_BCA", "Bank BCA (KlikBCA Bisnis / MCM)", "BANK", "REFERENCE_BASED", "BcaParser", 1, now_ts),
            ("BANK_MANDIRI", "Bank Mandiri (Kopra by Mandiri / MCM)", "BANK", "REFERENCE_BASED", "MandiriParser", 1, now_ts),
            ("BANK_BNI", "Bank BNI (BNI Direct)", "BANK", "REFERENCE_BASED", "BniParser", 1, now_ts),
            ("BANK_BRI", "Bank BRI (CMS BRI)", "BANK", "REFERENCE_BASED", "BriParser", 1, now_ts),
            ("BANK_MT940", "SWIFT MT940 / CAMT.053 Standard", "BANK", "REFERENCE_BASED", "Mt940Parser", 1, now_ts),
            ("MARKETPLACE_TIKTOK", "TikTok Shop Seller Center", "MARKETPLACE", "BATCH_BASED", "TiktokShopParser", 1, now_ts),
            ("MARKETPLACE_SHOPEE", "Shopee Seller Centre", "MARKETPLACE", "BATCH_BASED", "ShopeeParser", 1, now_ts),
            ("PAYMENT_GATEWAY_DOKU", "DOKU Payment Gateway", "PAYMENT_GATEWAY", "BATCH_BASED", "DokuParser", 1, now_ts),
            ("POS_CASH", "Kasir POS Tunai Toko Fisik", "POS", "BATCH_BASED", "PosCashParser", 1, now_ts),
            ("LOGISTICS_JNE_COD", "JNE Express COD Settlement", "LOGISTICS_COD", "COD_THREE_WAY", "JneCodParser", 1, now_ts),
            ("LOGISTICS_SICEPAT_COD", "SiCepat Express COD Settlement", "LOGISTICS_COD", "COD_THREE_WAY", "SicepatCodParser", 1, now_ts),
        ]
        cursor.executemany("""
            INSERT INTO source_channels (channel_id, channel_name, channel_type, matching_strategy, parser_class, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, builtin_sources)

    # Seed User Demo Bawaan jika kosong (Password: demo123)
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        # demo123 PBKDF2 hash
        demo_hash = "68c92b21764c6dbf69d311545fc86d11$e45eb488a0ad122485e92750e322f67645068222956cf9969ef332f170f4eeef"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO users (id, name, email, password_hash, store_name, plan, trial_runs_used, max_trial_runs, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "user-demo",
            "Merchant Demo",
            "demo@reconauto.id",
            demo_hash,
            "PT Rekon Auto Retail",
            "FREE_TRIAL",
            0,
            2,
            now_str
        ))

    # Seed Workspaces Default jika kosong
    cursor.execute("SELECT COUNT(*) FROM workspaces")
    if cursor.fetchone()[0] == 0:
        default_workspaces = [
            (
                "ws-default",
                "PT Rekon Auto Retail (Pusat)",
                "01.882.910.1-012.000",
                "Bank BCA KCU Thamrin",
                "8820-192-881",
                json.dumps({
                    "bank_account": "1-1001",
                    "tiktok_clearing": "1-1020",
                    "shopee_clearing": "1-1021",
                    "doku_clearing": "1-1022",
                    "cash_pos": "1-1010",
                    "platform_fee": "6-2001",
                    "cash_shortage": "6-9001",
                    "bank_interest": "8-1001",
                    "bank_fee": "6-3001",
                    "tax_interest": "6-3002"
                }),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ),
            (
                "ws-fashion",
                "Official Store Fashion & Apparel",
                "02.341.567.8-034.000",
                "Bank BCA KCP Grand Indonesia",
                "5410-881-229",
                json.dumps({
                    "bank_account": "1-1002",
                    "tiktok_clearing": "1-1030",
                    "shopee_clearing": "1-1031",
                    "doku_clearing": "1-1032",
                    "cash_pos": "1-1011",
                    "platform_fee": "6-2010",
                    "cash_shortage": "6-9002",
                    "bank_interest": "8-1002",
                    "bank_fee": "6-3003",
                    "tax_interest": "6-3004"
                }),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ),
            (
                "ws-gadget",
                "Toko Elektronik Makmur ID",
                "03.991.223.4-045.000",
                "Bank Mandiri KCP Sudirman",
                "122-00-981273-1",
                json.dumps({
                    "bank_account": "1-1003",
                    "tiktok_clearing": "1-1040",
                    "shopee_clearing": "1-1041",
                    "doku_clearing": "1-1042",
                    "cash_pos": "1-1012",
                    "platform_fee": "6-2020",
                    "cash_shortage": "6-9003",
                    "bank_interest": "8-1003",
                    "bank_fee": "6-3005",
                    "tax_interest": "6-3006"
                }),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        ]
        cursor.executemany("""
            INSERT INTO workspaces (id, name, tax_id, default_bank_name, default_account_num, coa_mapping_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, default_workspaces)

    conn.commit()
    conn.close()

def save_reconciliation_run(
    result: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None
) -> str:
    """
    Menyimpan sesi rekonsiliasi lengkap ke dalam SQLite.
    Mengembalikan run_id unik.
    """
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    metadata = metadata or {}
    now = datetime.now()
    run_id = f"RUN-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
    run_date = now.strftime("%Y-%m-%d %H:%M:%S")

    summary = result.get("summary", {})
    batches = result.get("batches", [])
    txns = result.get("transactions", [])
    bank_rows = result.get("bank_rows", [])
    discrepancies = result.get("discrepancies", [])

    # 1. Simpan Run Header
    ws_id = metadata.get("workspace_id", "ws-default")
    user_id = metadata.get("user_id", "user-demo")
    cursor.execute("""
    INSERT INTO reconciliation_runs (
        id, user_id, workspace_id, run_date, period_start, period_end, source_description,
        total_gross, total_fees, total_net, total_bank_cleared,
        bank_total_credits, bank_total_debits, in_transit_amount, missing_payout_amount,
        proof_difference, is_balanced, match_rate_pct,
        transactions_count, batches_count, exceptions_count,
        raw_summary_json, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        run_id,
        user_id,
        ws_id,
        run_date,
        metadata.get("period_start", ""),
        metadata.get("period_end", ""),
        metadata.get("source", "Sistem Rekonsiliasi Otomatis"),
        summary.get("total_gross_sales", 0.0),
        summary.get("total_platform_fees", 0.0),
        summary.get("total_expected_net", 0.0),
        summary.get("total_bank_cleared", 0.0),
        summary.get("bank_total_credits", 0.0),
        summary.get("bank_total_debits", 0.0),
        summary.get("in_transit_amount", 0.0),
        summary.get("missing_payout_amount", 0.0),
        summary.get("proof_difference", 0.0),
        1 if summary.get("is_balanced", True) else 0,
        summary.get("match_rate_pct", 0.0),
        len(txns),
        len(batches),
        len(discrepancies),
        json.dumps(summary),
        run_date
    ))

    # 2. Simpan Batches
    for b in batches:
        status = b.get("status", "UNMATCHED")
        is_open = 1 if status in ["TIMING_LAG", "CASH_IN_DRAWER"] else 0
        cursor.execute("""
        INSERT INTO stored_batches (
            run_id, batch_id, channel, settlement_date, order_count,
            gross_sum, fee_sum, net_sum, bank_matched, bank_date,
            bank_amount, difference, status, notes, is_open_in_transit
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            b.get("batch_id", ""),
            b.get("channel", ""),
            b.get("settlement_date", ""),
            b.get("order_count", 0),
            b.get("gross_sum", 0.0),
            b.get("fee_sum", 0.0),
            b.get("net_sum", 0.0),
            1 if b.get("bank_matched", False) else 0,
            b.get("bank_date"),
            b.get("bank_amount", 0.0),
            b.get("difference", 0.0),
            status,
            b.get("notes", ""),
            is_open
        ))

    # 3. Simpan Transaksi Kanonikal
    for t in txns:
        cursor.execute("""
        INSERT INTO stored_transactions (
            run_id, txn_id, channel, date, description,
            gross_amount, fee_amount, net_amount, batch_id,
            raw_status, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            t.get("txn_id", ""),
            t.get("channel", ""),
            t.get("date", ""),
            t.get("description", ""),
            t.get("gross_amount", 0.0),
            t.get("fee_amount", 0.0),
            t.get("net_amount", 0.0),
            t.get("batch_id", ""),
            t.get("raw_status", ""),
            json.dumps(t.get("metadata", {}))
        ))

    # 4. Simpan Mutasi Bank
    for bk in bank_rows:
        cursor.execute("""
        INSERT INTO stored_bank_rows (
            run_id, row_id, date, description, amount, txn_type,
            balance, matched, matched_batch_id, bank_code, account_number
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            bk.get("row_id", ""),
            bk.get("date", ""),
            bk.get("description", ""),
            bk.get("amount", 0.0),
            bk.get("txn_type", "CR"),
            bk.get("balance"),
            1 if bk.get("matched", False) else 0,
            bk.get("matched_batch_id"),
            bk.get("bank_code", "BCA"),
            bk.get("account_number")
        ))

    # 5. Simpan Discrepancies
    for d in discrepancies:
        cursor.execute("""
        INSERT INTO stored_discrepancies (
            run_id, disc_id, direction, channel, reference_id,
            date, issue_type, severity, expected_amount, actual_amount,
            discrepancy_amount, probable_cause, recommended_action, resolution_status, channel_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            d.get("id", ""),
            d.get("direction", ""),
            d.get("channel", ""),
            d.get("reference_id", ""),
            d.get("date", ""),
            d.get("issue_type", ""),
            d.get("severity", "MEDIUM"),
            d.get("expected_amount", 0.0),
            d.get("actual_amount", 0.0),
            d.get("discrepancy_amount", 0.0),
            d.get("probable_cause", ""),
            d.get("recommended_action", ""),
            "OPEN",
            d.get("channel", "")
        ))

    # 6. Simpan Settlement COD Kurir (Fase 3A)
    cod_settlements = result.get("cod_settlements", [])
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for c in cod_settlements:
        cursor.execute("""
        INSERT INTO stored_cod_settlements (
            run_id, awb_number, courier_name, order_id, cod_amount,
            courier_fee, net_remitted, settlement_date, bank_ref_id,
            status, metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            c.get("awb_number", ""),
            c.get("courier_name", ""),
            c.get("order_id", ""),
            c.get("cod_amount", 0.0),
            c.get("courier_fee", 0.0),
            c.get("net_remitted", 0.0),
            c.get("settlement_date", ""),
            c.get("bank_ref_id"),
            c.get("status", "PENDING"),
            json.dumps(c.get("metadata", {})),
            now_ts
        ))

    conn.commit()
    conn.close()
    return run_id

def get_reconciliation_runs(limit: int = 50, workspace_id: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Mengambil daftar riwayat sesi rekonsiliasi yang tersimpan di SQLite."""
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    if workspace_id:
        cursor.execute("""
            SELECT id, workspace_id, run_date, source_description, total_gross, total_net,
                   total_bank_cleared, in_transit_amount, missing_payout_amount, proof_difference,
                   is_balanced, match_rate_pct, transactions_count, batches_count, exceptions_count,
                   created_at
            FROM reconciliation_runs
            WHERE workspace_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (workspace_id, limit))
    else:
        cursor.execute("""
            SELECT id, workspace_id, run_date, source_description, total_gross, total_net,
                   total_bank_cleared, in_transit_amount, missing_payout_amount, proof_difference,
                   is_balanced, match_rate_pct, transactions_count, batches_count, exceptions_count,
                   created_at
            FROM reconciliation_runs
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_run_by_id(run_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Memuat data sesi rekonsiliasi lengkap berdasarkan run_id."""
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM reconciliation_runs WHERE id = ?", (run_id,))
    run_row = cursor.fetchone()
    if not run_row:
        conn.close()
        return None

    run_dict = dict(run_row)
    summary = json.loads(run_dict.get("raw_summary_json") or "{}")

    # Ambil batches
    cursor.execute("SELECT * FROM stored_batches WHERE run_id = ?", (run_id,))
    batches = [dict(r) for r in cursor.fetchall()]

    # Ambil transactions
    cursor.execute("SELECT * FROM stored_transactions WHERE run_id = ?", (run_id,))
    txns = []
    for r in cursor.fetchall():
        td = dict(r)
        td["metadata"] = json.loads(td.get("metadata_json") or "{}")
        txns.append(td)

    # Ambil bank rows
    cursor.execute("SELECT * FROM stored_bank_rows WHERE run_id = ?", (run_id,))
    bank_rows = [dict(r) for r in cursor.fetchall()]

    # Ambil discrepancies
    cursor.execute("SELECT * FROM stored_discrepancies WHERE run_id = ?", (run_id,))
    discrepancies = [dict(r) for r in cursor.fetchall()]

    # Ambil COD settlements (Fase 3A)
    cursor.execute("SELECT * FROM stored_cod_settlements WHERE run_id = ?", (run_id,))
    cod_settlements = []
    for r in cursor.fetchall():
        cd = dict(r)
        cd["metadata"] = json.loads(cd.get("metadata_json") or "{}")
        cod_settlements.append(cd)

    conn.close()

    return {
        "run_id": run_id,
        "workspace_id": run_dict.get("workspace_id", "ws-default"),
        "run_date": run_dict.get("run_date"),
        "source": run_dict.get("source_description"),
        "summary": summary,
        "batches": batches,
        "transactions": txns,
        "bank_rows": bank_rows,
        "discrepancies": discrepancies,
        "cod_settlements": cod_settlements,
        "transactions_count": len(txns)
    }

def get_open_in_transit_batches(workspace_id: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Mengambil seluruh batch payout dari periode lampau yang masih berstatus
    terbuka / belum klop dengan bank (In-Transit) untuk proses rolling settlement.
    """
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    if workspace_id:
        cursor.execute("""
            SELECT b.*, r.run_date as origin_run_date
            FROM stored_batches b
            JOIN reconciliation_runs r ON b.run_id = r.id
            WHERE b.is_open_in_transit = 1 AND r.workspace_id = ?
            ORDER BY b.settlement_date ASC
        """, (workspace_id,))
    else:
        cursor.execute("""
            SELECT b.*, r.run_date as origin_run_date
            FROM stored_batches b
            JOIN reconciliation_runs r ON b.run_id = r.id
            WHERE b.is_open_in_transit = 1
            ORDER BY b.settlement_date ASC
        """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def mark_batch_resolved_rolling(
    batch_id: str,
    resolution_run_id: str,
    bank_row_id: str,
    bank_date: str,
    db_path: Optional[str] = None
):
    """
    Menandai batch in-transit dari periode lampau telah berhasil klop/lunas
    pada sesi rekonsiliasi periode baru.
    """
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        UPDATE stored_batches
        SET is_open_in_transit = 0,
            status = 'RESOLVED_ROLLING',
            resolved_in_run_id = ?,
            bank_date = ?,
            notes = 'Klop dari periode sebelumnya via mutasi bank ' || ?,
            resolved_at = ?
        WHERE batch_id = ? AND is_open_in_transit = 1
    """, (resolution_run_id, bank_date, bank_row_id, now, batch_id))

    conn.commit()
    conn.close()

def get_rolling_summary(workspace_id: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Ringkasan status dana bergulir lintas periode."""
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    if workspace_id:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_open_count,
                COALESCE(SUM(b.net_sum), 0) as total_open_nominal
            FROM stored_batches b
            JOIN reconciliation_runs r ON b.run_id = r.id
            WHERE b.is_open_in_transit = 1 AND r.workspace_id = ?
        """, (workspace_id,))
        open_stats = dict(cursor.fetchone())

        cursor.execute("""
            SELECT 
                COUNT(*) as total_resolved_count,
                COALESCE(SUM(b.net_sum), 0) as total_resolved_nominal
            FROM stored_batches b
            JOIN reconciliation_runs r ON b.run_id = r.id
            WHERE b.status = 'RESOLVED_ROLLING' AND r.workspace_id = ?
        """, (workspace_id,))
        resolved_stats = dict(cursor.fetchone())

        cursor.execute("SELECT COUNT(*) as total_runs FROM reconciliation_runs WHERE workspace_id = ?", (workspace_id,))
        runs_count = cursor.fetchone()["total_runs"]
    else:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_open_count,
                COALESCE(SUM(net_sum), 0) as total_open_nominal
            FROM stored_batches b
            WHERE is_open_in_transit = 1
        """)
        open_stats = dict(cursor.fetchone())

        cursor.execute("""
            SELECT 
                COUNT(*) as total_resolved_count,
                COALESCE(SUM(net_sum), 0) as total_resolved_nominal
            FROM stored_batches b
            WHERE status = 'RESOLVED_ROLLING'
        """)
        resolved_stats = dict(cursor.fetchone())

        cursor.execute("SELECT COUNT(*) as total_runs FROM reconciliation_runs")
        runs_count = cursor.fetchone()["total_runs"]

    conn.close()
    return {
        "total_runs": runs_count,
        "open_in_transit_count": open_stats["total_open_count"],
        "open_in_transit_nominal": open_stats["total_open_nominal"],
        "resolved_rolling_count": resolved_stats["total_resolved_count"],
        "resolved_rolling_nominal": resolved_stats["total_resolved_nominal"]
    }

def get_workspaces(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Mengambil daftar seluruh entitas bisnis / toko yang terdaftar."""
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workspaces ORDER BY created_at ASC")
    rows = []
    for r in cursor.fetchall():
        d = dict(r)
        d["coa_mapping"] = json.loads(d.get("coa_mapping_json") or "{}")
        rows.append(d)
    conn.close()
    return rows

def get_workspace_by_id(ws_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Mengambil detail profil entitas toko beserta pemetaan COA."""
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    d = dict(row)
    d["coa_mapping"] = json.loads(d.get("coa_mapping_json") or "{}")
    conn.close()
    return d

def save_workspace(ws_data: Dict[str, Any], db_path: Optional[str] = None):
    """Menyimpan atau memperbarui entitas toko dan konfigurasi COA-nya."""
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    ws_id = ws_data.get("id") or f"ws-{int(datetime.now().timestamp())}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    coa_json = json.dumps(ws_data.get("coa_mapping", {}))

    cursor.execute("""
        INSERT INTO workspaces (id, name, tax_id, default_bank_name, default_account_num, coa_mapping_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            tax_id = excluded.tax_id,
            default_bank_name = excluded.default_bank_name,
            default_account_num = excluded.default_account_num,
            coa_mapping_json = excluded.coa_mapping_json
    """, (
        ws_id,
        ws_data.get("name", "Toko Baru"),
        ws_data.get("tax_id", "-"),
        ws_data.get("default_bank_name", "Bank BCA"),
        ws_data.get("default_account_num", "-"),
        coa_json,
        now
    ))
    conn.commit()
    conn.close()
    return ws_id

def save_accounting_sync_log(log_data: Dict[str, Any], db_path: Optional[str] = None) -> str:
    """Menyimpan catatan rekam jejak (audit trail) sinkronisasi jurnal ke software akuntansi."""
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    log_id = f"SYNC-{int(datetime.now().timestamp() * 1000)}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO accounting_sync_logs (
            id, workspace_id, run_id, provider, journal_ref_number,
            entry_count, total_debit, total_credit, payload_json,
            response_json, status, synced_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        log_id,
        log_data.get("workspace_id", "ws-default"),
        log_data.get("run_id", "RUN-ACTIVE"),
        log_data.get("provider", "MEKARI_JURNAL"),
        log_data.get("journal_ref_number", f"JRN-{datetime.now().strftime('%Y%m%d%H%M')}"),
        log_data.get("entry_count", 0),
        log_data.get("total_debit", 0.0),
        log_data.get("total_credit", 0.0),
        json.dumps(log_data.get("payload", {})),
        json.dumps(log_data.get("response", {})),
        log_data.get("status", "SUCCESS"),
        now
    ))
    conn.commit()
    conn.close()
    return log_id

def get_accounting_sync_logs(
    workspace_id: Optional[str] = None,
    limit: int = 50,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Mengambil daftar riwayat sinkronisasi API akuntansi."""
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    if workspace_id:
        cursor.execute("""
            SELECT l.*, w.name as workspace_name
            FROM accounting_sync_logs l
            JOIN workspaces w ON l.workspace_id = w.id
            WHERE l.workspace_id = ?
            ORDER BY l.synced_at DESC
            LIMIT ?
        """, (workspace_id, limit))
    else:
        cursor.execute("""
            SELECT l.*, w.name as workspace_name
            FROM accounting_sync_logs l
            JOIN workspaces w ON l.workspace_id = w.id
            ORDER BY l.synced_at DESC
            LIMIT ?
        """, (limit,))

    rows = []
    for r in cursor.fetchall():
        d = dict(r)
        d["payload"] = json.loads(d.get("payload_json") or "{}")
        d["response"] = json.loads(d.get("response_json") or "{}")
        rows.append(d)

    conn.close()
    return rows

def get_cod_settlements(run_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Mengambil riwayat pencairan COD kurir untuk suatu run."""
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stored_cod_settlements WHERE run_id = ? ORDER BY id ASC", (run_id,))
    rows = []
    for r in cursor.fetchall():
        d = dict(r)
        d["metadata"] = json.loads(d.get("metadata_json") or "{}")
        rows.append(d)
    conn.close()
    return rows

def get_source_channels(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Mengambil seluruh sumber data terdaftar dari registry basis data."""
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM source_channels ORDER BY created_at ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def register_source_channel(
    channel_id: str,
    channel_name: str,
    channel_type: str,
    matching_strategy: str,
    parser_class: Optional[str] = None,
    is_active: bool = True,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """Mendaftarkan atau memperbarui kanal sumber baru di registry database."""
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO source_channels (channel_id, channel_name, channel_type, matching_strategy, parser_class, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(channel_id) DO UPDATE SET
            channel_name = excluded.channel_name,
            channel_type = excluded.channel_type,
            matching_strategy = excluded.matching_strategy,
            parser_class = excluded.parser_class,
            is_active = excluded.is_active
    """, (channel_id, channel_name, channel_type, matching_strategy, parser_class, 1 if is_active else 0, now_ts))

    conn.commit()
    conn.close()
    return {
        "channel_id": channel_id,
        "channel_name": channel_name,
        "channel_type": channel_type,
        "matching_strategy": matching_strategy,
        "is_active": is_active
    }


