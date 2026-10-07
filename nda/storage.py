"""
Penyimpanan record persetujuan NDA ke basis data SQLite rekonsile.db
dengan fallback/sinkronisasi ke file JSON untuk audit trail independen.
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from typing import List, Optional

from .models import NDAConsentRecord

logger = logging.getLogger("reconauto.nda.storage")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DB_PATH = _PROJECT_ROOT / "rekonsile.db"
_STORAGE_DIR = _PROJECT_ROOT / "data"
_STORAGE_FILE = _STORAGE_DIR / "nda_consents.json"


def _ensure_sqlite_table() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nda_consents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        consent_id TEXT UNIQUE NOT NULL,
        nama_lengkap TEXT NOT NULL,
        email TEXT NOT NULL,
        nama_perusahaan TEXT,
        jabatan TEXT,
        document_version TEXT,
        document_hash TEXT,
        signature_data TEXT,
        timestamp_utc TEXT,
        timestamp_wib TEXT,
        ip_address TEXT,
        user_agent TEXT,
        created_at TEXT DEFAULT (datetime('now', 'localtime'))
    );
    """)
    conn.commit()
    return conn


def _ensure_json_storage() -> None:
    _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    if not _STORAGE_FILE.exists():
        _STORAGE_FILE.write_text("[]", encoding="utf-8")


def save_consent(record: NDAConsentRecord) -> None:
    """Simpan record consent ke SQLite rekonsile.db dan file JSON."""
    # 1. Simpan ke SQLite
    try:
        conn = _ensure_sqlite_table()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT OR REPLACE INTO nda_consents (
            consent_id, nama_lengkap, email, nama_perusahaan, jabatan,
            document_version, document_hash, signature_data,
            timestamp_utc, timestamp_wib, ip_address, user_agent
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.consent_id,
            record.nama_lengkap,
            record.email,
            record.nama_perusahaan,
            record.jabatan,
            record.document_version,
            record.document_hash,
            record.signature_data,
            record.timestamp_utc,
            record.timestamp_wib,
            record.ip_address,
            record.user_agent
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Gagal simpan ke SQLite, menggunakan fallback JSON: {e}")

    # 2. Simpan ke JSON (backup)
    try:
        _ensure_json_storage()
        try:
            data = json.loads(_STORAGE_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = []
        data.append(record.model_dump())
        _STORAGE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.error(f"Gagal simpan ke JSON: {e}")

    logger.info(f"NDA consent tersimpan di SQLite & JSON: {record.consent_id} ({record.email})")


def find_by_email(email: str) -> Optional[NDAConsentRecord]:
    """Cari consent terbaru berdasarkan email dari SQLite rekonsile.db."""
    clean_email = email.strip().lower()
    try:
        conn = _ensure_sqlite_table()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nda_consents WHERE LOWER(email) = ? ORDER BY id DESC LIMIT 1", (clean_email,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return NDAConsentRecord(**dict(row))
    except Exception as e:
        logger.warning(f"Gagal membaca dari SQLite: {e}")

    # Fallback ke JSON
    try:
        _ensure_json_storage()
        data = json.loads(_STORAGE_FILE.read_text(encoding="utf-8"))
        for item in reversed(data):
            if item.get("email", "").strip().lower() == clean_email:
                return NDAConsentRecord(**item)
    except Exception:
        pass
    return None


def find_by_consent_id(consent_id: str) -> Optional[NDAConsentRecord]:
    """Cari consent berdasarkan UUID consent_id untuk verifikasi."""
    try:
        conn = _ensure_sqlite_table()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nda_consents WHERE consent_id = ? LIMIT 1", (consent_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return NDAConsentRecord(**dict(row))
    except Exception as e:
        logger.warning(f"Gagal membaca dari SQLite: {e}")

    # Fallback JSON
    try:
        _ensure_json_storage()
        data = json.loads(_STORAGE_FILE.read_text(encoding="utf-8"))
        for item in data:
            if item.get("consent_id") == consent_id:
                return NDAConsentRecord(**item)
    except Exception:
        pass
    return None


def get_all_consents() -> List[NDAConsentRecord]:
    """Ambil seluruh record consent."""
    try:
        conn = _ensure_sqlite_table()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nda_consents ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        return [NDAConsentRecord(**dict(r)) for r in rows]
    except Exception:
        return []
