"""
Model data Pydantic untuk modul NDA Digital ReconAuto.ID.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, EmailStr


class NDAConsentRequest(BaseModel):
    """Data yang dikirim saat pengguna menyetujui NDA."""
    nama_lengkap: str = Field(..., min_length=2, max_length=200,
                              description="Nama lengkap penandatangan")
    email: str = Field(..., min_length=5, max_length=254,
                       description="Alamat email aktif penandatangan",
                       pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    nama_perusahaan: Optional[str] = Field(None, max_length=300,
                                           description="Nama perusahaan/badan (opsional untuk individu)")
    jabatan: Optional[str] = Field(None, max_length=150,
                                   description="Jabatan di perusahaan (opsional)")
    checkbox_setuju: bool = Field(...,
                                  description="Wajib True — pengguna mencentang bahwa telah membaca & setuju")
    signature_data: Optional[str] = Field(None,
                                          description="Data tanda tangan digital (base64-encoded PNG dari canvas)")
    document_hash: str = Field(...,
                               description="Hash SHA-256 dokumen NDA yang ditampilkan, untuk verifikasi versi")


class NDAConsentRecord(BaseModel):
    """Record persetujuan yang disimpan di storage (audit trail)."""
    consent_id: str = Field(..., description="UUID unik untuk record consent ini")
    nama_lengkap: str
    email: str
    nama_perusahaan: Optional[str] = None
    jabatan: Optional[str] = None
    document_version: str
    document_hash: str
    signature_data: Optional[str] = None
    timestamp_utc: str = Field(..., description="ISO 8601 UTC")
    timestamp_wib: str = Field(..., description="ISO 8601 WIB (Asia/Jakarta)")
    ip_address: str
    user_agent: str


class NDAStatusResponse(BaseModel):
    """Response untuk endpoint cek status NDA."""
    has_consented: bool
    consent_id: Optional[str] = None
    consented_at: Optional[str] = None
    document_version: Optional[str] = None


class NDADocumentResponse(BaseModel):
    """Response untuk endpoint ambil teks NDA."""
    document_text: str
    document_version: str
    document_hash: str


class NDAVerifyResponse(BaseModel):
    """Response untuk endpoint verifikasi consent."""
    valid: bool
    consent_record: Optional[NDAConsentRecord] = None
    message: str
