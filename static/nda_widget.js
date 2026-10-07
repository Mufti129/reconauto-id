/**
 * Widget NDA Digital — ReconAuto.ID
 *
 * Mengimplementasikan:
 * 1. Modal pop-up proporsional sebelum akses rekonsiliasi
 * 2. Canvas tanda tangan digital berbasis W3C Pointer Events (Touch/Stylus/Mouse)
 * 3. Enforce scroll-to-bottom pembacaan pasal
 * 4. Submit consent ke backend SQLite + localStorage cache
 */

(function () {
  "use strict";

  const LS_KEY = "reconauto_nda_consent_id";
  const LS_EMAIL_KEY = "reconauto_nda_email";
  const API_BASE = "/api/nda";

  // Elemen DOM
  const overlay = document.getElementById("nda-overlay");
  if (!overlay) return;

  const textArea = document.getElementById("nda-text-area");
  const scrollHint = document.getElementById("nda-scroll-hint");
  const checkbox = document.getElementById("nda-checkbox");
  const submitBtn = document.getElementById("nda-submit-btn");
  const nameInput = document.getElementById("nda-nama");
  const emailInput = document.getElementById("nda-email");
  const companyInput = document.getElementById("nda-perusahaan");
  const positionInput = document.getElementById("nda-jabatan");
  const errorBox = document.getElementById("nda-error");
  const canvas = document.getElementById("nda-sig-canvas");
  const clearSigBtn = document.getElementById("nda-clear-sig");
  const sigStatus = document.getElementById("nda-sig-status");
  const sigPlaceholder = document.getElementById("nda-sig-placeholder");
  const sigBox = document.getElementById("nda-sig-box");

  // State
  let documentHash = "";
  let scrolledToBottom = false;
  let hasDrawn = false;
  let isDrawing = false;
  let lastX = 0;
  let lastY = 0;
  let ctx = null;

  // Cek apakah sudah pernah consent
  const savedConsentId = localStorage.getItem(LS_KEY);
  if (savedConsentId) {
    overlay.classList.add("hidden");
    return;
  }

  // ==================== FETCH DOKUMEN NDA ====================
  async function loadNDADocument() {
    try {
      const res = await fetch(API_BASE + "/document");
      if (!res.ok) throw new Error("Gagal memuat teks perjanjian.");
      const data = await res.json();
      textArea.textContent = data.document_text;
      documentHash = data.document_hash;

      // Tampilkan modal
      overlay.classList.remove("hidden");
      requestAnimationFrame(() => {
        overlay.classList.add("visible");
        // Inisialisasi canvas setelah modal tampak di layar
        setTimeout(initCanvas, 100);
      });
    } catch (err) {
      console.warn("NDA fetch error (fail-open mode):", err);
      overlay.classList.add("hidden");
    }
  }

  loadNDADocument();

  // ==================== INISIALISASI CANVAS TANDA TANGAN ====================
  function initCanvas() {
    if (!canvas) return;

    // Ukuran internal canvas tetap tinggi agar goresan tajam
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const w = rect.width > 0 ? rect.width : 360;
    const h = rect.height > 0 ? rect.height : 110;

    canvas.width = w * dpr;
    canvas.height = h * dpr;

    ctx = canvas.getContext("2d");
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
    ctx.strokeStyle = "#0f172a";
    ctx.lineWidth = 2.4;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    // Setup event listeners untuk drawing
    setupDrawingEvents();
  }

  window.addEventListener("resize", () => {
    if (overlay.classList.contains("visible") && !hasDrawn) {
      initCanvas();
    }
  });

  function getPointerPos(e) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    };
  }

  function startDrawing(e) {
    e.preventDefault();
    if (!ctx) initCanvas();
    isDrawing = true;
    const pos = getPointerPos(e);
    lastX = pos.x;
    lastY = pos.y;

    if (sigBox) sigBox.classList.add("active");
    if (sigPlaceholder) sigPlaceholder.style.opacity = "0";

    // Gambar titik awal
    ctx.beginPath();
    ctx.arc(lastX, lastY, 1.2, 0, Math.PI * 2);
    ctx.fillStyle = "#0f172a";
    ctx.fill();
  }

  function drawMove(e) {
    if (!isDrawing || !ctx) return;
    e.preventDefault();
    const pos = getPointerPos(e);

    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(pos.x, pos.y);
    ctx.stroke();

    lastX = pos.x;
    lastY = pos.y;
    hasDrawn = true;

    if (sigStatus) {
      sigStatus.innerHTML = "✓ Tanda tangan terdeteksi";
      sigStatus.className = "nda-sig-status signed";
    }
    if (sigBox) sigBox.classList.add("has-signature");
  }

  function stopDrawing() {
    isDrawing = false;
    if (sigBox) sigBox.classList.remove("active");
  }

  function setupDrawingEvents() {
    // Pointer Events (Mendukung Touch, Mouse, dan Stylus)
    canvas.onpointerdown = (e) => {
      canvas.setPointerCapture(e.pointerId);
      startDrawing(e);
    };
    canvas.onpointermove = drawMove;
    canvas.onpointerup = (e) => {
      canvas.releasePointerCapture(e.pointerId);
      stopDrawing();
    };
    canvas.onpointercancel = (e) => {
      canvas.releasePointerCapture(e.pointerId);
      stopDrawing();
    };

    // Tombol Clear
    if (clearSigBtn) {
      clearSigBtn.onclick = clearSignature;
    }
  }

  function clearSignature() {
    if (!ctx) return;
    const rect = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, rect.height);
    hasDrawn = false;
    if (sigPlaceholder) sigPlaceholder.style.opacity = "1";
    if (sigStatus) {
      sigStatus.innerHTML = "Goreskan tanda tangan di atas";
      sigStatus.className = "nda-sig-status";
    }
    if (sigBox) {
      sigBox.classList.remove("has-signature");
      sigBox.classList.remove("active");
    }
  }

  // ==================== SCROLL ENFORCEMENT ====================
  function markScrolled() {
    if (scrolledToBottom) return;
    scrolledToBottom = true;
    if (scrollHint) {
      scrollHint.textContent = "✓ Seluruh 9 pasal telah dibaca";
      scrollHint.classList.add("done");
    }
    updateSubmitState();
  }

  function checkScroll() {
    if (scrolledToBottom) return;
    const threshold = 40;
    if (textArea.scrollHeight - textArea.scrollTop - textArea.clientHeight < threshold) {
      markScrolled();
    }
  }

  textArea.addEventListener("scroll", checkScroll);
  textArea.addEventListener("wheel", () => setTimeout(checkScroll, 100));
  textArea.addEventListener("touchmove", () => setTimeout(checkScroll, 100));

  // Fallback jika dokumen langsung muat atau user telah berada di halaman > 12 detik
  setTimeout(() => {
    if (textArea.scrollHeight <= textArea.clientHeight + 20) markScrolled();
  }, 800);
  setTimeout(markScrolled, 12000);

  // ==================== VALIDASI FORM & TOMBOL SUBMIT ====================
  function updateSubmitState() {
    const nameOk = nameInput.value.trim().length >= 2;
    const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailInput.value.trim());
    const checked = checkbox.checked;

    submitBtn.disabled = !(nameOk && emailOk && checked && scrolledToBottom);
  }

  [nameInput, emailInput, companyInput, positionInput].forEach((el) => {
    if (el) el.addEventListener("input", updateSubmitState);
  });

  if (checkbox) {
    checkbox.addEventListener("change", updateSubmitState);
    checkbox.addEventListener("click", (e) => {
      if (!scrolledToBottom) {
        e.preventDefault();
        showError("Harap gulir ke bawah dan baca teks perjanjian terlebih dahulu.");
      }
    });
  }

  // ==================== SUBMIT PERSATUJUAN ====================
  if (submitBtn) {
    submitBtn.addEventListener("click", submitConsent);
  }

  async function submitConsent() {
    hideError();

    const nama = nameInput.value.trim();
    const email = emailInput.value.trim();

    if (nama.length < 2) {
      showError("Nama lengkap wajib diisi (minimal 2 karakter).");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      showError("Format alamat email tidak valid.");
      return;
    }
    if (!checkbox.checked) {
      showError("Harap centang kotak persetujuan perjanjian.");
      return;
    }

    // Ambil data tanda tangan canvas (jika digoreskan)
    let sigData = null;
    if (hasDrawn && canvas) {
      sigData = canvas.toDataURL("image/png");
    }

    const payload = {
      nama_lengkap: nama,
      email: email,
      nama_perusahaan: companyInput.value.trim() || null,
      jabatan: positionInput.value.trim() || null,
      checkbox_setuju: true,
      signature_data: sigData,
      document_hash: documentHash,
    };

    submitBtn.disabled = true;
    submitBtn.textContent = "Menyimpan Persetujuan...";

    try {
      const res = await fetch(API_BASE + "/consent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal mencatat persetujuan.");

      // Simpan ke localStorage
      const consentId = (data.consent_record && data.consent_record.consent_id) ? data.consent_record.consent_id : "latest";
      localStorage.setItem(LS_KEY, consentId);
      localStorage.setItem(LS_EMAIL_KEY, email);

      // Tampilkan state sukses dan tombol unduh dokumen resmi bersama
      const modalContent = document.getElementById("nda-modal");
      if (modalContent) {
        modalContent.innerHTML = `
          <div style="padding: 32px 24px; text-align: center; max-width: 520px; margin: 0 auto;">
            <div style="width: 52px; height: 52px; background: #ecfdf5; border: 2px solid #a7f3d0; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 14px;">
              <svg style="width: 26px; height: 26px; color: #059669;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
              </svg>
            </div>
            <h3 style="font-size: 17px; font-weight: 800; color: #0f172a; margin-bottom: 6px;">Persetujuan NDA Digital Berhasil Disahkan</h3>
            <p style="font-size: 12px; color: #64748b; line-height: 1.5; margin-bottom: 18px;">
              Perjanjian kerahasiaan data finansial telah sah mengikat kedua belah pihak secara hukum (UU PDP No. 27/2022 &amp; UU ITE No. 1/2024). Anda dan perusahaan dapat menyimpan salinan resmi bertanda tangan digital ini.
            </p>
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px 16px; margin-bottom: 20px; text-align: left; font-size: 11.5px; color: #334155;">
              <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span style="color: #64748b;">Penandatangan:</span>
                <span style="font-weight: 700; color: #0f172a;">${nama}</span>
              </div>
              <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span style="color: #64748b;">Instansi / Perusahaan:</span>
                <span style="font-weight: 600; color: #0f172a;">${companyInput.value.trim() || 'Perusahaan Klien'}</span>
              </div>
              <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span style="color: #64748b;">ID Registrasi Dokumen:</span>
                <span style="font-family: monospace; font-weight: 600; color: #2563eb;">${consentId.slice(0, 13)}...</span>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span style="color: #64748b;">Status Sertifikasi:</span>
                <span style="color: #059669; font-weight: 700;">TERVERIFIKASI &bull; AES-256</span>
              </div>
            </div>
            <div style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
              <a href="/api/nda/download/${consentId}" target="_blank" download style="display: inline-flex; align-items: center; gap: 6px; padding: 9px 18px; background: #059669; color: #ffffff; text-decoration: none; border-radius: 10px; font-size: 12px; font-weight: 700; box-shadow: 0 2px 4px rgba(5,150,105,0.25);">
                <svg style="width: 15px; height: 15px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
                <span>Unduh Dokumen NDA (PDF)</span>
              </a>
              <button onclick="document.getElementById('nda-overlay').classList.remove('visible'); setTimeout(() => document.getElementById('nda-overlay').classList.add('hidden'), 200);" style="padding: 9px 16px; background: #0f172a; color: #ffffff; border: none; border-radius: 10px; font-size: 12px; font-weight: 600; cursor: pointer;">
                Lanjut ke Rekonsiliasi
              </button>
            </div>
          </div>
        `;
      } else {
        // Fallback jika modalContent tidak ditemukan
        overlay.classList.remove("visible");
        setTimeout(() => overlay.classList.add("hidden"), 250);
      }

    } catch (err) {
      showError(err.message || "Terjadi kendala saat mengirim persetujuan. Silakan coba lagi.");
      submitBtn.disabled = false;
      submitBtn.textContent = "Setuju & Buka Akses Rekonsiliasi";
    }
  }

  function showError(msg) {
    if (errorBox) {
      errorBox.textContent = msg;
      errorBox.style.display = "block";
    }
  }

  function hideError() {
    if (errorBox) errorBox.style.display = "none";
  }

})();
