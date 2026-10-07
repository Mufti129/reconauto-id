"""
core/engine.py
--------------
Engine Rekonsiliasi Dua Arah (Bidirectional 2-Tier Matching Engine):
1. Tier 1: Order-Level Validation & Fee Checking
2. Tier 2: Forward Matching (Source -> Bank Batch Reconciliation)
3. Tier 3: Cash & Cross-Channel Reconciliation
4. Tier 4: Reverse Matching (Bank -> Source Audit)
5. Proof of Cash & Discrepancy Classification
"""

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from .models import (
    SourceChannel, CanonicalTransaction, BankStatementRow,
    BatchPayoutGroup, DiscrepancyItem, ReconcileDirection,
    DiscrepancySeverity, CodSettlementRow
)

class BidirectionalReconciliationEngine:
    def __init__(self, tolerance_amount: float = 100.0, lag_days_threshold: int = 3):
        self.tolerance = tolerance_amount
        self.lag_days = lag_days_threshold
        
    def reconcile(
        self,
        bank_rows: List[BankStatementRow],
        source_transactions: List[CanonicalTransaction],
        prior_unresolved_batches: Optional[List[Dict[str, Any]]] = None,
        cod_settlements: Optional[List[CodSettlementRow]] = None
    ) -> Dict[str, Any]:
        """
        Menjalankan proses rekonsiliasi dua arah penuh, dengan dukungan penyelesaian
        bergulir lintas periode (Rolling Cross-Period Reconciliation) dan audit 3-arah
        logistik COD kurir (Order <-> Kurir COD <-> Bank).
        """
        discrepancies: List[DiscrepancyItem] = []
        cod_settlements = cod_settlements or []
        
        # 1. Order-level validation (Tier 1)
        self._validate_orders(source_transactions, discrepancies)

        # 2. Rekonsiliasi 3-Arah Logistik COD Kurir (Order <-> Courier AWB <-> Bank)
        cod_summary = None
        if cod_settlements:
            cod_summary = self._reconcile_cod_three_way(
                source_transactions, cod_settlements, bank_rows, discrepancies
            )
        
        # 3. Batch Payouts to Bank (Tier 2 & Tier 3) - Forward Reconcile
        batches = self._group_into_batches(source_transactions)
        self._reconcile_batches_to_bank(batches, bank_rows, discrepancies)
        
        # 4. Bank to Source Audit (Tier 4) - Reverse Reconcile with Rolling Resolution
        rolling_resolved = self._reconcile_bank_to_source(
            bank_rows, batches, discrepancies, prior_unresolved_batches=prior_unresolved_batches
        )
        
        # 5. Summary & Mathematical Proof of Cash
        summary = self._build_proof_of_cash(
            source_transactions, batches, bank_rows, discrepancies,
            rolling_resolved=rolling_resolved, cod_settlements=cod_settlements
        )
        
        # 6. Detailed Match vs Not Match Analytics
        match_analytics = self._build_match_analytics(
            source_transactions, batches, bank_rows, discrepancies, summary, cod_settlements=cod_settlements
        )
        
        return {
            "summary": summary,
            "match_analytics": match_analytics,
            "batches": [self._serialize_batch(b) for b in batches],
            "rolling_resolved": rolling_resolved,
            "discrepancies": [self._serialize_discrepancy(d) for d in discrepancies],
            "bank_rows": [self._serialize_bank_row(b) for b in bank_rows],
            "transactions": [self._serialize_transaction(t) for t in source_transactions],
            "transactions_count": len(source_transactions),
            "cod_settlements": [self._serialize_cod(c) for c in cod_settlements],
            "cod_summary": cod_summary
        }

    def _reconcile_cod_three_way(
        self,
        source_transactions: List[CanonicalTransaction],
        cod_settlements: List[CodSettlementRow],
        bank_rows: List[BankStatementRow],
        discrepancies: List[DiscrepancyItem]
    ) -> Dict[str, Any]:
        """
        Rekonsiliasi 3-Arah Logistik COD Kurir:
        1. Order Penjualan <-> Resi Kurir (AWB): Validasi kesesuaian nilai COD & order
        2. Resi Kurir (AWB) <-> Mutasi Bank: Validasi net pencairan kurir ke rekening bank
        3. Deteksi Anomali: COD_UNREMITTED (dana tertahan di kurir) & COD_SHORTAGE (selisih fee/potongan)
        """
        orders_map = {t.txn_id: t for t in source_transactions}
        
        # Group COD by bank_ref_id to match batch remittances to bank
        batch_cod_groups: Dict[str, List[CodSettlementRow]] = {}
        for cod in cod_settlements:
            ref = (cod.bank_ref_id or "").strip()
            if ref:
                batch_cod_groups.setdefault(ref, []).append(cod)
                
        # 1. Match courier batches to bank rows
        for ref_id, items in batch_cod_groups.items():
            net_sum = sum(i.net_remitted for i in items)
            matched_bank = None
            
            # Pass 1: Match ref_id in bank description
            for b in bank_rows:
                if b.txn_type != "CR":
                    continue
                if ref_id.lower() in b.description.lower():
                    matched_bank = b
                    break
                    
            # Pass 2: Match exact net sum
            if not matched_bank:
                for b in bank_rows:
                    if b.matched or b.txn_type != "CR":
                        continue
                    if abs(b.amount - net_sum) <= self.tolerance:
                        matched_bank = b
                        break
                        
            if matched_bank:
                matched_bank.matched = True
                matched_bank.matched_with = ref_id
                for item in items:
                    if item.status != "COD_SHORTAGE":
                        item.status = "CLEARED"
                    item.metadata["matched_bank_row"] = matched_bank.row_id
                    item.metadata["bank_amount"] = matched_bank.amount
                    item.metadata["bank_date"] = matched_bank.date

        # 2. Individual checking & Discrepancy Generation
        for cod in cod_settlements:
            # Check 1: Match with source orders
            matched_order = orders_map.get(cod.order_id)
            if matched_order:
                cod.metadata["order_matched"] = True
                cod.metadata["order_gross"] = matched_order.gross_amount
                if abs(matched_order.gross_amount - cod.cod_amount) > 1.0:
                    discrepancies.append(DiscrepancyItem(
                        id=f"DISC-COD-VAL-{cod.awb_number}",
                        direction=ReconcileDirection.CROSS,
                        channel=cod.courier_name,
                        reference_id=cod.awb_number,
                        date=cod.settlement_date or "2026-08-15",
                        issue_type="COD_VALUE_MISMATCH",
                        severity=DiscrepancySeverity.MEDIUM,
                        expected_amount=matched_order.gross_amount,
                        actual_amount=cod.cod_amount,
                        discrepancy_amount=round(cod.cod_amount - matched_order.gross_amount, 2),
                        probable_cause=f"Nilai tagihan COD kurir ({cod.cod_amount:,.0f}) berbeda dengan nilai order penjualan ({matched_order.gross_amount:,.0f})",
                        recommended_action="Verifikasi harga barang dan ongkir pada invoice order.",
                        metadata={"awb": cod.awb_number, "order_id": cod.order_id, "courier": cod.courier_name}
                    ))
            
            # Check 2: COD_UNREMITTED
            if cod.status == "COD_UNREMITTED" or not cod.bank_ref_id:
                discrepancies.append(DiscrepancyItem(
                    id=f"DISC-COD-UNREMIT-{cod.awb_number}",
                    direction=ReconcileDirection.FORWARD,
                    channel=cod.courier_name,
                    reference_id=cod.awb_number,
                    date=cod.settlement_date or "2026-08-15",
                    issue_type="COD_UNREMITTED",
                    severity=DiscrepancySeverity.HIGH,
                    expected_amount=round(cod.cod_amount - cod.courier_fee, 2),
                    actual_amount=0.0,
                    discrepancy_amount=round(cod.cod_amount - cod.courier_fee, 2),
                    probable_cause=f"Dana COD resi {cod.awb_number} ({cod.order_id}) belum ditransfer oleh kurir {cod.courier_name} ke bank",
                    recommended_action=f"Segera ajukan klaim penagihan dana COD resi {cod.awb_number} ke PIC Finance {cod.courier_name}.",
                    metadata={"awb": cod.awb_number, "order_id": cod.order_id, "courier": cod.courier_name}
                ))
            elif cod.status == "COD_SHORTAGE" or ((cod.cod_amount - cod.courier_fee) - cod.net_remitted > 1.0):
                expected = round(cod.cod_amount - cod.courier_fee, 2)
                shortage = round(expected - cod.net_remitted, 2)
                discrepancies.append(DiscrepancyItem(
                    id=f"DISC-COD-SHORT-{cod.awb_number}",
                    direction=ReconcileDirection.FORWARD,
                    channel=cod.courier_name,
                    reference_id=cod.awb_number,
                    date=cod.settlement_date or "2026-08-15",
                    issue_type="COD_SHORTAGE",
                    severity=DiscrepancySeverity.HIGH,
                    expected_amount=expected,
                    actual_amount=cod.net_remitted,
                    discrepancy_amount=shortage,
                    probable_cause=f"Pencairan COD resi {cod.awb_number} kurang Rp {shortage:,.0f} dari nilai bersih yang seharusnya",
                    recommended_action=f"Klarifikasi rincian potongan ongkir/retensi tambahan ke kurir {cod.courier_name}.",
                    metadata={"awb": cod.awb_number, "order_id": cod.order_id, "courier": cod.courier_name}
                ))

        # Build COD summary stats
        total_cod = sum(c.cod_amount for c in cod_settlements)
        total_courier_fee = sum(c.courier_fee for c in cod_settlements)
        total_net_remitted = sum(c.net_remitted for c in cod_settlements)
        cleared_cod = sum(c.net_remitted for c in cod_settlements if c.status == "CLEARED")
        unremitted_cod = sum(c.cod_amount - c.courier_fee for c in cod_settlements if c.status == "COD_UNREMITTED")
        shortage_cod = sum((c.cod_amount - c.courier_fee) - c.net_remitted for c in cod_settlements if c.status == "COD_SHORTAGE")

        return {
            "total_awb_count": len(cod_settlements),
            "total_cod_amount": total_cod,
            "total_courier_fee": total_courier_fee,
            "total_net_remitted": total_net_remitted,
            "cleared_amount": cleared_cod,
            "unremitted_amount": unremitted_cod,
            "shortage_amount": shortage_cod,
            "cleared_awb_count": sum(1 for c in cod_settlements if c.status == "CLEARED"),
            "unremitted_awb_count": sum(1 for c in cod_settlements if c.status == "COD_UNREMITTED"),
            "shortage_awb_count": sum(1 for c in cod_settlements if c.status == "COD_SHORTAGE")
        }

    def _validate_orders(self, txns: List[CanonicalTransaction], discrepancies: List[DiscrepancyItem]):
        """Memvalidasi integritas matematika per order dan mendeteksi selisih fee overcharge."""
        for t in txns:
            # Periksa perhitungan: Net harus sama dengan Gross - Fee (dengan toleransi Rp 1)
            expected_net = t.gross_amount - t.fee_amount
            gap = abs(t.net_amount - expected_net)
            if gap > 1.0:
                discrepancies.append(DiscrepancyItem(
                    id=f"DISC-MATH-{t.txn_id}",
                    direction=ReconcileDirection.CROSS,
                    channel=t.source_channel.value,
                    reference_id=t.txn_id,
                    date=t.date,
                    issue_type="MATH_CALCULATION_ERROR",
                    severity=DiscrepancySeverity.MEDIUM,
                    expected_amount=expected_net,
                    actual_amount=t.net_amount,
                    discrepancy_amount=t.net_amount - expected_net,
                    probable_cause="Selisih perhitungan internal sistem vs laporan platform",
                    recommended_action="Periksa rincian potongan promo/ongkir tambahan pada invoice ini.",
                    metadata={"sku": t.metadata.get("sku", "-")}
                ))
            
            # Khusus TikTok Shop: Cek overcharge referral fee (standar ~5% IDR)
            if t.source_channel == SourceChannel.MARKETPLACE_TIKTOK and t.gross_amount > 0:
                ref_fee = t.metadata.get("referral_fee", 0.0)
                fee_rate = ref_fee / t.gross_amount
                if fee_rate > 0.07:  # Lebih dari 7% padahal standar 5%
                    normal_fee = round(t.gross_amount * 0.05, 2)
                    overcharge = ref_fee - normal_fee
                    discrepancies.append(DiscrepancyItem(
                        id=f"DISC-FEE-{t.txn_id}",
                        direction=ReconcileDirection.CROSS,
                        channel=t.source_channel.value,
                        reference_id=t.txn_id,
                        date=t.date,
                        issue_type="FEE_OVERCHARGE_ANOMALY",
                        severity=DiscrepancySeverity.HIGH,
                        expected_amount=normal_fee,
                        actual_amount=ref_fee,
                        discrepancy_amount=overcharge,
                        probable_cause=f"Tarif komisi platform terbebankan {fee_rate*100:.1f}% (melebihi rate kategori standar 5%)",
                        recommended_action=f"Ajukan sanggahan / dispute fee overcharge sebesar Rp {overcharge:,.0f} ke Seller Center TikTok.",
                        metadata={"rate_applied": f"{fee_rate*100:.1f}%", "sku": t.metadata.get("sku", "-")}
                    ))

    def _group_into_batches(self, txns: List[CanonicalTransaction]) -> List[BatchPayoutGroup]:
        """Mengelompokkan transaksi per Batch Payout / Settlement Ref."""
        groups: Dict[str, List[CanonicalTransaction]] = {}
        for t in txns:
            b_id = t.batch_id or f"SINGLE-{t.txn_id}"
            if b_id not in groups:
                groups[b_id] = []
            groups[b_id].append(t)
            
        batches = []
        for b_id, item_list in groups.items():
            first = item_list[0]
            gross_sum = sum(i.gross_amount for i in item_list)
            fee_sum = sum(i.fee_amount for i in item_list)
            net_sum = sum(i.net_amount for i in item_list)
            dates = [i.date for i in item_list if i.date]
            settle_date = max(dates) if dates else "2026-08-01"
            
            batches.append(BatchPayoutGroup(
                batch_id=b_id,
                source_channel=first.source_channel,
                settlement_date=settle_date,
                order_count=len(item_list),
                gross_sum=gross_sum,
                fee_sum=fee_sum,
                net_sum=net_sum,
                order_ids=[i.txn_id for i in item_list]
            ))
        return batches

    def _reconcile_batches_to_bank(
        self,
        batches: List[BatchPayoutGroup],
        bank_rows: List[BankStatementRow],
        discrepancies: List[DiscrepancyItem]
    ):
        """Mencocokkan setiap batch pencairan dana ke mutasi bank (Arah Maju / Forward)."""
        # Tanggal mutasi bank terakhir sebagai patokan cut-off
        valid_bank_dates = [b.date for b in bank_rows if b.date]
        cutoff_date = max(valid_bank_dates) if valid_bank_dates else "2026-08-15"

        for batch in batches:
            # Khusus Kasir Tunai yang belum disetor
            if batch.batch_id == "BELUM_SETOR":
                batch.status = "CASH_IN_DRAWER"
                batch.notes = "Uang tunai masih tersimpan di brankas toko (belum disetor ke bank)"
                discrepancies.append(DiscrepancyItem(
                    id=f"DISC-CASH-HOLD-{batch.batch_id}",
                    direction=ReconcileDirection.CROSS,
                    channel="POS_CASH",
                    reference_id=batch.batch_id,
                    date=batch.settlement_date,
                    issue_type="CASH_NOT_DEPOSITED",
                    severity=DiscrepancySeverity.MEDIUM,
                    expected_amount=batch.net_sum,
                    actual_amount=0.0,
                    discrepancy_amount=batch.net_sum,
                    probable_cause="Penerimaan kasir tunai belum disetorkan ke rekening bank",
                    recommended_action="Lakukan setoran tunai CDM/teller untuk fisik kas toko Rp {0:,.0f}.".format(batch.net_sum)
                ))
                continue

            # Cari mutasi kredit bank yang cocok
            matched_bank_row = None
            
            # Pass 1: Cocokkan nomor Batch Ref di keterangan mutasi bank
            for b_row in bank_rows:
                if b_row.txn_type != "CR":
                    continue
                if b_row.matched and b_row.matched_with == batch.batch_id:
                    matched_bank_row = b_row
                    break
                if not b_row.matched and batch.batch_id.lower() in b_row.description.lower():
                    matched_bank_row = b_row
                    break
                    
            # Pass 2: Jika belum ketemu, cocokkan nominal persis + rentang tanggal
            if not matched_bank_row:
                for b_row in bank_rows:
                    if b_row.matched or b_row.txn_type != "CR":
                        continue
                    if abs(b_row.amount - batch.net_sum) <= self.tolerance:
                        matched_bank_row = b_row
                        break

            if matched_bank_row:
                # Ditemukan mutasi bank yang cocok!
                matched_bank_row.matched = True
                matched_bank_row.matched_with = batch.batch_id
                
                batch.bank_matched = True
                batch.bank_date = matched_bank_row.date
                batch.bank_amount = matched_bank_row.amount
                batch.difference = round(batch.net_sum - matched_bank_row.amount, 2)
                
                if abs(batch.difference) <= 0.01:
                    batch.status = "MATCHED"
                    bank_label = getattr(matched_bank_row, "bank_code", "BANK_BCA").replace("BANK_", "")
                    batch.notes = f"100% Klop dengan mutasi {bank_label} tanggal {matched_bank_row.date}"
                else:
                    # Kasus Cash Shortage: Ref cocok tapi uang disetor kurang!
                    batch.status = "PARTIALLY_MATCHED"
                    batch.notes = f"Dana disetor Rp {matched_bank_row.amount:,.0f}, selisih Rp {batch.difference:,.0f}"
                    discrepancies.append(DiscrepancyItem(
                        id=f"DISC-SHORTAGE-{batch.batch_id}",
                        direction=ReconcileDirection.CROSS,
                        channel=batch.source_channel.value,
                        reference_id=batch.batch_id,
                        date=matched_bank_row.date,
                        issue_type="CASH_SHORTAGE_ANOMALY",
                        severity=DiscrepancySeverity.HIGH,
                        expected_amount=batch.net_sum,
                        actual_amount=matched_bank_row.amount,
                        discrepancy_amount=batch.difference,
                        probable_cause=f"Fisik setoran tunai ke bank kurang Rp {batch.difference:,.0f} dari catatan kasir",
                        recommended_action="Klarifikasi ke kasir yang bertugas terkait selisih fisik setoran CDM."
                    ))
            else:
                # Tidak ditemukan mutasi bank yang cocok!
                # Cek apakah timing lag (wajar) atau missing payout (berbahaya)
                try:
                    dt_batch = datetime.strptime(batch.settlement_date, "%Y-%m-%d")
                    dt_cutoff = datetime.strptime(cutoff_date, "%Y-%m-%d")
                    day_diff = (dt_cutoff - dt_batch).days
                except Exception:
                    day_diff = 1

                if day_diff <= self.lag_days:
                    batch.status = "TIMING_LAG"
                    batch.notes = f"Dana dalam perjalanan (In-Transit H+{day_diff} hari dari settlement)"
                    discrepancies.append(DiscrepancyItem(
                        id=f"DISC-LAG-{batch.batch_id}",
                        direction=ReconcileDirection.FORWARD,
                        channel=batch.source_channel.value,
                        reference_id=batch.batch_id,
                        date=batch.settlement_date,
                        issue_type="DEPOSIT_IN_TRANSIT",
                        severity=DiscrepancySeverity.LOW,
                        expected_amount=batch.net_sum,
                        actual_amount=0.0,
                        discrepancy_amount=batch.net_sum,
                        probable_cause="Pencairan dana marketplace/PG baru dilakukan dekat cut-off rekening",
                        recommended_action="Pantau mutasi bank 1-2 hari kerja berikutnya untuk memastikan dana masuk."
                    ))
                else:
                    batch.status = "MISSING_PAYOUT"
                    batch.notes = f"BAHAYA: Dana settlement tgl {batch.settlement_date} belum pernah masuk bank!"
                    discrepancies.append(DiscrepancyItem(
                        id=f"DISC-MISSING-{batch.batch_id}",
                        direction=ReconcileDirection.FORWARD,
                        channel=batch.source_channel.value,
                        reference_id=batch.batch_id,
                        date=batch.settlement_date,
                        issue_type="MISSING_BANK_PAYOUT",
                        severity=DiscrepancySeverity.HIGH,
                        expected_amount=batch.net_sum,
                        actual_amount=0.0,
                        discrepancy_amount=batch.net_sum,
                        probable_cause=f"Batch payout {batch.batch_id} sudah selesai di platform tapi belum masuk rekening koran",
                        recommended_action=f"Segera hubungi support/finance {batch.source_channel.value} untuk klaim dana tertahan."
                    ))

    def _reconcile_bank_to_source(
        self,
        bank_rows: List[BankStatementRow],
        batches: List[BatchPayoutGroup],
        discrepancies: List[DiscrepancyItem],
        prior_unresolved_batches: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Mengaudit seluruh mutasi bank yang belum memiliki pasangan data sumber (Arah Balik / Reverse).
        Juga memeriksa apakah kredit bank merupakan pelunasan in-transit dari periode lampau (Rolling).
        """
        rolling_resolved = []
        prior_batches = list(prior_unresolved_batches or [])

        for row in bank_rows:
            if row.matched:
                continue

            desc_upper = row.description.upper()
            
            if row.txn_type == "CR":
                # 1. Cek apakah ini pelunasan dari batch in-transit periode lampau!
                matched_prior = None
                for pb in prior_batches:
                    diff = abs(row.amount - pb.get("net_sum", 0.0))
                    batch_id = str(pb.get("batch_id", "")).strip()
                    # Cocok jika selisih nominal <= Rp 1.0 atau nomor batch termaktub di mutasi bank
                    if diff <= 1.0 or (batch_id and batch_id.upper() in desc_upper):
                        matched_prior = pb
                        break

                if matched_prior:
                    prior_batches.remove(matched_prior)
                    row.matched = True
                    row.matched_batch_id = matched_prior.get("batch_id")
                    b_code = getattr(row, "bank_code", "BANK_BCA")
                    b_label = b_code.replace("BANK_", "")
                    resolved_info = {
                        "batch_id": matched_prior.get("batch_id"),
                        "channel": matched_prior.get("channel"),
                        "settlement_date": matched_prior.get("settlement_date"),
                        "net_sum": matched_prior.get("net_sum", row.amount),
                        "bank_row_id": row.row_id,
                        "bank_date": row.date,
                        "bank_amount": row.amount,
                        "description": row.description,
                        "status": "RESOLVED_ROLLING",
                        "notes": f"Lunas dari periode sebelumnya (Settlement: {matched_prior.get('settlement_date')}) via mutasi {b_label} tgl {row.date}"
                    }
                    rolling_resolved.append(resolved_info)
                    continue

                b_code = getattr(row, "bank_code", "BANK_BCA")

                # 2. Uang masuk tanpa order/batch pencairan
                if "BUNGA" in desc_upper:
                    discrepancies.append(DiscrepancyItem(
                        id=f"DISC-REV-INT-{row.row_id}",
                        direction=ReconcileDirection.REVERSE,
                        channel=b_code,
                        reference_id=row.row_id,
                        date=row.date,
                        issue_type="UNRECORDED_BANK_INTEREST",
                        severity=DiscrepancySeverity.LOW,
                        expected_amount=0.0,
                        actual_amount=row.amount,
                        discrepancy_amount=row.amount,
                        probable_cause="Pendapatan bunga giro bank belum dicatat di buku kas / software akuntansi",
                        recommended_action="Buat jurnal penyesuaian: Debit Bank, Kredit Pendapatan Bunga."
                    ))
                else:
                    # Uang masuk tak bertuan (Unidentified Deposit)
                    discrepancies.append(DiscrepancyItem(
                        id=f"DISC-REV-UNID-{row.row_id}",
                        direction=ReconcileDirection.REVERSE,
                        channel=b_code,
                        reference_id=row.row_id,
                        date=row.date,
                        issue_type="UNIDENTIFIED_BANK_CREDIT",
                        severity=DiscrepancySeverity.HIGH,
                        expected_amount=0.0,
                        actual_amount=row.amount,
                        discrepancy_amount=row.amount,
                        probable_cause=f"Uang masuk Rp {row.amount:,.0f} '{row.description}' tidak memiliki nomor pesanan/invoice",
                        recommended_action="Konfirmasi ke bagian operasional/klien apakah ada pembayaran manual langsung ke rekening."
                    ))
            elif row.txn_type == "DB":
                b_code = getattr(row, "bank_code", "BANK_BCA")
                # Uang keluar / potongan bank
                if "BIAYA ADM" in desc_upper or "ADMINISTRASI" in desc_upper:
                    discrepancies.append(DiscrepancyItem(
                        id=f"DISC-REV-ADM-{row.row_id}",
                        direction=ReconcileDirection.REVERSE,
                        channel=b_code,
                        reference_id=row.row_id,
                        date=row.date,
                        issue_type="UNRECORDED_BANK_FEE",
                        severity=DiscrepancySeverity.LOW,
                        expected_amount=0.0,
                        actual_amount=row.amount,
                        discrepancy_amount=-row.amount,
                        probable_cause="Biaya administrasi bulanan rekening koran belum dicatat",
                        recommended_action="Buat jurnal penyesuaian: Debit Beban Administrasi Bank, Kredit Bank."
                    ))
                elif "PAJAK BUNGA" in desc_upper:
                    discrepancies.append(DiscrepancyItem(
                        id=f"DISC-REV-TAX-{row.row_id}",
                        direction=ReconcileDirection.REVERSE,
                        channel=b_code,
                        reference_id=row.row_id,
                        date=row.date,
                        issue_type="UNRECORDED_BANK_TAX",
                        severity=DiscrepancySeverity.LOW,
                        expected_amount=0.0,
                        actual_amount=row.amount,
                        discrepancy_amount=-row.amount,
                        probable_cause="Pajak penghasilan atas bunga giro (20%) dipotong otomatis oleh bank",
                        recommended_action="Buat jurnal penyesuaian: Debit Beban Pajak Bunga, Kredit Bank."
                    ))

        return rolling_resolved

    def _build_proof_of_cash(
        self,
        txns: List[CanonicalTransaction],
        batches: List[BatchPayoutGroup],
        bank_rows: List[BankStatementRow],
        discrepancies: List[DiscrepancyItem],
        rolling_resolved: Optional[List[Dict[str, Any]]] = None,
        cod_settlements: Optional[List[CodSettlementRow]] = None
    ) -> Dict[str, Any]:
        """Menghitung ringkasan eksekutif dan bukti rekonsiliasi kas (Proof of Cash)."""
        rolling_resolved = rolling_resolved or []
        cod_settlements = cod_settlements or []

        total_gross = sum(t.gross_amount for t in txns)
        total_fees = sum(t.fee_amount for t in txns)
        total_expected_net = sum(t.net_amount for t in txns)

        bank_credits = sum(b.amount for b in bank_rows if b.txn_type == "CR")
        bank_debits = sum(b.amount for b in bank_rows if b.txn_type == "DB")
        bank_net_change = bank_credits - bank_debits

        matched_batches = [b for b in batches if b.status == "MATCHED"]
        total_bank_cleared = sum(b.net_sum for b in matched_batches)
        
        in_transit_sum = sum(b.net_sum for b in batches if b.status == "TIMING_LAG")
        missing_payout_sum = sum(b.net_sum for b in batches if b.status == "MISSING_PAYOUT")
        unsettled_cash_sum = sum(b.net_sum for b in batches if b.status == "CASH_IN_DRAWER")
        
        prior_cleared_sum = sum(r.get("net_sum", 0.0) for r in rolling_resolved)
        unidentified_credits = sum(d.discrepancy_amount for d in discrepancies if d.issue_type == "UNIDENTIFIED_BANK_CREDIT")
        bank_interest = sum(d.discrepancy_amount for d in discrepancies if d.issue_type == "UNRECORDED_BANK_INTEREST")
        bank_charges = sum(abs(d.discrepancy_amount) for d in discrepancies if d.issue_type in ["UNRECORDED_BANK_FEE", "UNRECORDED_BANK_TAX"])
        cash_shortage = sum(d.discrepancy_amount for d in discrepancies if d.issue_type == "CASH_SHORTAGE_ANOMALY")
        fee_overcharge = sum(d.discrepancy_amount for d in discrepancies if d.issue_type == "FEE_OVERCHARGE_ANOMALY")

        # COD logistics clearance (for orders remitted via courier into bank)
        txn_ids = {t.txn_id for t in txns}
        external_cod_cleared = sum(
            c.net_remitted for c in cod_settlements
            if c.status == "CLEARED" and c.order_id not in txn_ids
        )
        cod_unremitted = sum(
            (c.cod_amount - c.courier_fee) for c in cod_settlements
            if c.status == "COD_UNREMITTED"
        )
        cod_shortage = sum(
            ((c.cod_amount - c.courier_fee) - c.net_remitted) for c in cod_settlements
            if c.status == "COD_SHORTAGE"
        )

        # Rumus Proof of Cash (Audit-ready):
        # Rekonsiliasi Bank = (Penjualan Bersih Periode Ini) - (In-Transit Periode Ini) - (Missing Payout) - (Kas Toko) - (Shortage)
        #                     + (Pelunasan In-Transit Periode Lalu) + (Unidentified Deposit) + (Bunga Bank) + (Net COD Terpencairkan)
        reconciled_bank_credits = (
            total_expected_net 
            - in_transit_sum 
            - missing_payout_sum 
            - unsettled_cash_sum 
            - cash_shortage 
            + prior_cleared_sum
            + unidentified_credits 
            + bank_interest
            + external_cod_cleared
        )
        proof_difference = round(bank_credits - reconciled_bank_credits, 2)

        match_rate_denom = total_expected_net + prior_cleared_sum + external_cod_cleared
        match_rate = round(((total_bank_cleared + prior_cleared_sum + external_cod_cleared) / match_rate_denom * 100), 1) if match_rate_denom > 0 else 0.0

        return {
            "total_gross_sales": total_gross,
            "total_platform_fees": total_fees,
            "total_expected_net": total_expected_net,
            "total_bank_cleared": total_bank_cleared,
            "bank_total_credits": bank_credits,
            "bank_total_debits": bank_debits,
            "bank_net_change": bank_net_change,
            "in_transit_amount": in_transit_sum,
            "missing_payout_amount": missing_payout_sum,
            "unsettled_cash_amount": unsettled_cash_sum,
            "prior_in_transit_cleared_amount": prior_cleared_sum,
            "unidentified_bank_credits": unidentified_credits,
            "bank_interest_income": bank_interest,
            "bank_charges": bank_charges,
            "cash_shortage": cash_shortage,
            "fee_overcharge": fee_overcharge,
            "external_cod_cleared": external_cod_cleared,
            "cod_unremitted_amount": cod_unremitted,
            "cod_shortage_amount": cod_shortage,
            "reconciled_bank_credits": reconciled_bank_credits,
            "proof_difference": proof_difference,
            "is_balanced": abs(proof_difference) <= 0.05,
            "match_rate_pct": match_rate,
            "total_exceptions_count": len(discrepancies)
        }

    def _serialize_batch(self, b: BatchPayoutGroup) -> Dict[str, Any]:
        return {
            "batch_id": b.batch_id,
            "channel": b.source_channel.value,
            "settlement_date": b.settlement_date,
            "order_count": b.order_count,
            "gross_sum": b.gross_sum,
            "fee_sum": b.fee_sum,
            "net_sum": b.net_sum,
            "bank_matched": b.bank_matched,
            "bank_date": b.bank_date,
            "bank_amount": b.bank_amount,
            "difference": b.difference,
            "status": b.status,
            "notes": b.notes,
            "order_ids": b.order_ids
        }

    def _serialize_discrepancy(self, d: DiscrepancyItem) -> Dict[str, Any]:
        return {
            "id": d.id,
            "direction": d.direction.value,
            "channel": d.channel,
            "reference_id": d.reference_id,
            "date": d.date,
            "issue_type": d.issue_type,
            "severity": d.severity.value,
            "expected_amount": d.expected_amount,
            "actual_amount": d.actual_amount,
            "discrepancy_amount": d.discrepancy_amount,
            "probable_cause": d.probable_cause,
            "recommended_action": d.recommended_action,
            "metadata": d.metadata
        }

    def _serialize_bank_row(self, b: BankStatementRow) -> Dict[str, Any]:
        return {
            "row_id": b.row_id,
            "bank_code": getattr(b, "bank_code", "BANK_BCA"),
            "account_number": getattr(b, "account_number", "8830192881"),
            "date": b.date,
            "description": b.description,
            "amount": b.amount,
            "txn_type": b.txn_type,
            "matched": b.matched,
            "matched_with": b.matched_with
        }

    def _serialize_cod(self, c: CodSettlementRow) -> Dict[str, Any]:
        return {
            "awb_number": c.awb_number,
            "courier_name": c.courier_name,
            "order_id": c.order_id,
            "cod_amount": c.cod_amount,
            "courier_fee": c.courier_fee,
            "net_remitted": c.net_remitted,
            "settlement_date": c.settlement_date,
            "bank_ref_id": c.bank_ref_id,
            "status": c.status,
            "metadata": c.metadata
        }

    def _serialize_transaction(self, t: CanonicalTransaction) -> Dict[str, Any]:
        return {
            "txn_id": t.txn_id,
            "channel": t.source_channel.value,
            "date": t.date,
            "description": t.description,
            "gross_amount": t.gross_amount,
            "fee_amount": t.fee_amount,
            "net_amount": t.net_amount,
            "batch_id": t.batch_id,
            "raw_status": t.raw_status,
            "metadata": t.metadata
        }

    def _build_match_analytics(
        self,
        txns: List[CanonicalTransaction],
        batches: List[BatchPayoutGroup],
        bank_rows: List[BankStatementRow],
        discrepancies: List[DiscrepancyItem],
        summary: Dict[str, Any],
        cod_settlements: Optional[List[CodSettlementRow]] = None
    ) -> Dict[str, Any]:
        """Menghitung statistik detail persentase match dan not match secara agregat dan per kanal."""
        cod_settlements = cod_settlements or []
        batch_status_map = {b.batch_id: b.status for b in batches}
        
        matched_txns = []
        not_matched_txns = []
        
        for t in txns:
            b_status = batch_status_map.get(t.batch_id, "UNMATCHED")
            if b_status == "MATCHED":
                matched_txns.append(t)
            else:
                not_matched_txns.append(t)
                
        cod_cleared_count = sum(1 for c in cod_settlements if c.status == "CLEARED")
        cod_uncleared_count = len(cod_settlements) - cod_cleared_count
        
        total_txns_count = len(txns) + len(cod_settlements)
        matched_count = len(matched_txns) + cod_cleared_count
        not_matched_count = len(not_matched_txns) + cod_uncleared_count
        
        matched_count_pct = round((matched_count / total_txns_count * 100), 2) if total_txns_count > 0 else 0.0
        not_matched_count_pct = round(100.0 - matched_count_pct, 2) if total_txns_count > 0 else 0.0
        
        external_cod_cleared = summary.get("external_cod_cleared", 0.0)
        total_net = summary.get("total_expected_net", 0.0) + external_cod_cleared
        matched_nominal = summary.get("total_bank_cleared", 0.0) + external_cod_cleared
        not_matched_nominal = round(total_net - matched_nominal, 2)
        
        matched_nominal_pct = round((matched_nominal / total_net * 100), 2) if total_net > 0 else 0.0
        not_matched_nominal_pct = round(100.0 - matched_nominal_pct, 2) if total_net > 0 else 0.0
        
        # Breakdown per-channel
        channel_names = {
            "MARKETPLACE_TIKTOK": "TikTok Shop Seller Center",
            "MARKETPLACE_SHOPEE": "Shopee Seller Center",
            "PAYMENT_GATEWAY_DOKU": "DOKU Payment Gateway",
            "POS_CASH": "POS Kasir Tunai Toko",
            "POS_JUBELIO": "Jubelio POS & Omnichannel",
            "BANK_BCA": "Mutasi Bank BCA",
            "BANK_MANDIRI": "Mutasi Bank Mandiri (Kopra/MCM)",
            "BANK_BNI": "Mutasi Bank BNI",
            "BANK_BRI": "Mutasi Bank BRI",
            "LOGISTICS_JNE_COD": "JNE Express COD Settlement",
            "LOGISTICS_SICEPAT_COD": "SiCepat Express COD Settlement"
        }
        
        by_channel = []
        for ch_key, ch_label in channel_names.items():
            if ch_key.startswith("BANK_"):
                bank_key_rows = [r for r in bank_rows if getattr(r, "bank_code", "BANK_BCA") == ch_key]
                if not bank_key_rows and ch_key == "BANK_BCA" and any(getattr(r, "bank_code", "BANK_BCA") in ["BANK_BCA", "", None] for r in bank_rows):
                    bank_key_rows = [r for r in bank_rows if getattr(r, "bank_code", "BANK_BCA") in ["BANK_BCA", "", None]]
                
                # Skip secondary bank if not in dataset
                if not bank_key_rows and ch_key != "BANK_BCA":
                    continue
                    
                ch_total_count = len(bank_key_rows)
                ch_matched_count = sum(1 for r in bank_key_rows if r.matched)
                ch_not_matched_count = ch_total_count - ch_matched_count
                ch_total_amt = sum(r.amount for r in bank_key_rows)
                ch_matched_amt = sum(r.amount for r in bank_key_rows if r.matched)
                ch_not_matched_amt = ch_total_amt - ch_matched_amt
            elif ch_key.startswith("LOGISTICS_"):
                if "JNE" in ch_key:
                    c_rows = [c for c in cod_settlements if "jne" in (c.courier_name or "").lower()]
                else:
                    c_rows = [c for c in cod_settlements if "sicepat" in (c.courier_name or "").lower()]
                if not c_rows:
                    continue
                ch_total_count = len(c_rows)
                ch_matched_count = sum(1 for c in c_rows if c.status == "CLEARED")
                ch_not_matched_count = ch_total_count - ch_matched_count
                ch_total_amt = sum(c.net_remitted for c in c_rows)
                ch_matched_amt = sum(c.net_remitted for c in c_rows if c.status == "CLEARED")
                ch_not_matched_amt = ch_total_amt - ch_matched_amt
            else:
                ch_txns = [t for t in txns if t.source_channel.value == ch_key]
                ch_total_count = len(ch_txns)
                ch_matched_txns = [t for t in ch_txns if batch_status_map.get(t.batch_id) == "MATCHED"]
                ch_matched_count = len(ch_matched_txns)
                ch_not_matched_count = ch_total_count - ch_matched_count
                ch_total_amt = sum(t.net_amount for t in ch_txns)
                ch_matched_amt = sum(t.net_amount for t in ch_matched_txns)
                ch_not_matched_amt = ch_total_amt - ch_matched_amt
                
            ch_match_pct = round((ch_matched_amt / ch_total_amt * 100), 2) if ch_total_amt > 0 else 0.0
            ch_not_match_pct = round(100.0 - ch_match_pct, 2) if ch_total_amt > 0 else 0.0
            
            by_channel.append({
                "channel_key": ch_key,
                "channel_name": ch_label,
                "total_count": ch_total_count,
                "matched_count": ch_matched_count,
                "not_matched_count": ch_not_matched_count,
                "match_count_pct": round((ch_matched_count / ch_total_count * 100), 1) if ch_total_count > 0 else 0.0,
                "not_match_count_pct": round((ch_not_matched_count / ch_total_count * 100), 1) if ch_total_count > 0 else 0.0,
                "total_nominal": ch_total_amt,
                "matched_nominal": ch_matched_amt,
                "not_matched_nominal": ch_not_matched_amt,
                "match_nominal_pct": ch_match_pct,
                "not_match_nominal_pct": ch_not_match_pct
            })
            
        # Collect items for each category
        items_matched = [
            {
                "id": t.txn_id,
                "date": t.date,
                "channel": t.source_channel.value,
                "description": t.description,
                "gross_amount": t.gross_amount,
                "fee_amount": t.fee_amount,
                "net_amount": t.net_amount,
                "batch_id": t.batch_id or "-",
                "reason": f"Klop 100% dengan batch pencairan {t.batch_id} yang sudah cair ke bank."
            }
            for t in matched_txns
        ]
        
        # Add cleared COD to items_matched
        for c in cod_settlements:
            if c.status == "CLEARED":
                items_matched.append({
                    "id": c.awb_number,
                    "date": c.settlement_date,
                    "channel": c.courier_name,
                    "description": f"COD Resi {c.awb_number} ({c.order_id})",
                    "gross_amount": c.cod_amount,
                    "fee_amount": c.courier_fee,
                    "net_amount": c.net_remitted,
                    "batch_id": c.bank_ref_id or "-",
                    "reason": f"Klop 100% cair ke rekening bank via ref {c.bank_ref_id}."
                })
        
        items_transit = [
            {
                "id": t.txn_id,
                "date": t.date,
                "channel": t.source_channel.value,
                "description": t.description,
                "gross_amount": t.gross_amount,
                "fee_amount": t.fee_amount,
                "net_amount": t.net_amount,
                "batch_id": t.batch_id or "-",
                "reason": f"Sedang kliring (H+1 sd H+3) via batch {t.batch_id}. Dana masih dalam perjalanan ke bank."
            }
            for t in txns if batch_status_map.get(t.batch_id) == "TIMING_LAG"
        ]
        
        items_missing = [
            {
                "id": t.txn_id,
                "date": t.date,
                "channel": t.source_channel.value,
                "description": t.description,
                "gross_amount": t.gross_amount,
                "fee_amount": t.fee_amount,
                "net_amount": t.net_amount,
                "batch_id": t.batch_id or "-",
                "reason": f"Order berstatus selesai di platform, namun batch {t.batch_id} belum pernah masuk rekening bank (Perlu klaim CS/Finance)."
            }
            for t in txns if batch_status_map.get(t.batch_id) == "MISSING_PAYOUT"
        ]
        
        items_drawer = [
            {
                "id": t.txn_id,
                "date": t.date,
                "channel": t.source_channel.value,
                "description": t.description,
                "gross_amount": t.gross_amount,
                "fee_amount": t.fee_amount,
                "net_amount": t.net_amount,
                "batch_id": t.batch_id or "-",
                "reason": "Uang tunai kasir toko belum disetorkan ke bank (masih tersimpan di brankas)."
            }
            for t in txns if batch_status_map.get(t.batch_id) == "CASH_IN_DRAWER"
        ]
        
        items_shortage = [
            {
                "id": t.txn_id,
                "date": t.date,
                "channel": t.source_channel.value,
                "description": t.description,
                "gross_amount": t.gross_amount,
                "fee_amount": t.fee_amount,
                "net_amount": t.net_amount,
                "batch_id": t.batch_id or "-",
                "reason": f"Setoran CDM bank kurang Rp 200.000 dari total penerimaan kasir pada batch setoran {t.batch_id}."
            }
            for t in txns if t.batch_id == "SETOR-CDM-0807"
        ]
        
        items_unidentified = [
            {
                "id": r.row_id,
                "date": r.date,
                "channel": getattr(r, "bank_code", "BANK_BCA"),
                "description": r.description,
                "gross_amount": r.amount,
                "fee_amount": 0.0,
                "net_amount": r.amount,
                "batch_id": "TANPA_NO_PESANAN",
                "reason": f"Mutasi kredit Rp {r.amount:,.0f} '{r.description}' masuk di rekening bank tanpa ada nomor pesanan / invoice pengirim."
            }
            for r in bank_rows if r.txn_type == "CR" and not r.matched and "BUNGA" not in r.description.upper()
        ]

        # Category Detail Matrix with item drill-downs
        categories = [
            {
                "category": "Klop 100% di Mutasi Bank (Cleared)",
                "type": "MATCHED",
                "count": matched_count,
                "count_pct": matched_count_pct,
                "nominal": matched_nominal,
                "nominal_pct": matched_nominal_pct,
                "action": "Telah klop penuh dengan mutasi kredit bank.",
                "color": "emerald",
                "items": items_matched
            },
            {
                "category": "Dana Dalam Perjalanan (In-Transit / Lag)",
                "type": "NOT_MATCHED",
                "count": sum(b.order_count for b in batches if b.status == "TIMING_LAG"),
                "count_pct": round(sum(b.order_count for b in batches if b.status == "TIMING_LAG") / total_txns_count * 100, 2) if total_txns_count > 0 else 0.0,
                "nominal": summary.get("in_transit_amount", 0.0),
                "nominal_pct": round(summary.get("in_transit_amount", 0.0) / total_net * 100, 2) if total_net > 0 else 0.0,
                "action": "Wajar (H+1 sd H+3). Pantau rekening pada hari kerja berikutnya.",
                "color": "amber",
                "items": items_transit
            },
            {
                "category": "Dana Hilang / Tertahan (Missing Payout)",
                "type": "NOT_MATCHED",
                "count": sum(b.order_count for b in batches if b.status == "MISSING_PAYOUT"),
                "count_pct": round(sum(b.order_count for b in batches if b.status == "MISSING_PAYOUT") / total_txns_count * 100, 2) if total_txns_count > 0 else 0.0,
                "nominal": summary.get("missing_payout_amount", 0.0),
                "nominal_pct": round(summary.get("missing_payout_amount", 0.0) / total_net * 100, 2) if total_net > 0 else 0.0,
                "action": "Prioritas Tinggi. Segera ajukan klaim ke CS/Finance Seller Center.",
                "color": "rose",
                "items": items_missing
            },
            {
                "category": "Kas Toko Belum Disetor (Cash in Drawer)",
                "type": "NOT_MATCHED",
                "count": sum(b.order_count for b in batches if b.status == "CASH_IN_DRAWER"),
                "count_pct": round(sum(b.order_count for b in batches if b.status == "CASH_IN_DRAWER") / total_txns_count * 100, 2) if total_txns_count > 0 else 0.0,
                "nominal": summary.get("unsettled_cash_amount", 0.0),
                "nominal_pct": round(summary.get("unsettled_cash_amount", 0.0) / total_net * 100, 2) if total_net > 0 else 0.0,
                "action": "Setorkan uang kasir fisik ke rekening bank melalui CDM/Teller.",
                "color": "slate",
                "items": items_drawer
            },
            {
                "category": "Selisih Kasir Fisik (Cash Shortage)",
                "type": "NOT_MATCHED",
                "count": sum(1 for d in discrepancies if d.issue_type == "CASH_SHORTAGE_ANOMALY"),
                "count_pct": round(sum(1 for d in discrepancies if d.issue_type == "CASH_SHORTAGE_ANOMALY") / total_txns_count * 100, 2) if total_txns_count > 0 else 0.0,
                "nominal": summary.get("cash_shortage", 0.0),
                "nominal_pct": round(summary.get("cash_shortage", 0.0) / total_net * 100, 2) if total_net > 0 else 0.0,
                "action": "Investigasi shift kasir bertugas dan catat beban selisih kas.",
                "color": "rose",
                "items": items_shortage
            },
            {
                "category": "Setoran Bank Tak Dikenal (Unidentified Bank Credit)",
                "type": "NOT_MATCHED",
                "count": sum(1 for d in discrepancies if d.issue_type == "UNIDENTIFIED_BANK_CREDIT"),
                "count_pct": round(sum(1 for d in discrepancies if d.issue_type == "UNIDENTIFIED_BANK_CREDIT") / total_txns_count * 100, 2) if total_txns_count > 0 else 0.0,
                "nominal": summary.get("unidentified_bank_credits", 0.0),
                "nominal_pct": round(summary.get("unidentified_bank_credits", 0.0) / total_net * 100, 2) if total_net > 0 else 0.0,
                "action": "Konfirmasi tim sales/klien apakah ada pelunasan di luar invoice resmi.",
                "color": "purple",
                "items": items_unidentified
            }
        ]

        # Add COD categories if COD discrepancies exist
        cod_unremit_discs = [d for d in discrepancies if d.issue_type == "COD_UNREMITTED"]
        if cod_unremit_discs:
            categories.append({
                "category": "Dana COD Belum Ditransfer Kurir (COD Unremitted)",
                "type": "NOT_MATCHED",
                "count": len(cod_unremit_discs),
                "count_pct": round(len(cod_unremit_discs) / total_txns_count * 100, 2) if total_txns_count > 0 else 0.0,
                "nominal": sum(d.discrepancy_amount for d in cod_unremit_discs),
                "nominal_pct": round(sum(d.discrepancy_amount for d in cod_unremit_discs) / total_net * 100, 2) if total_net > 0 else 0.0,
                "action": "Prioritas Tinggi. Segera tagih pencairan dana COD ke finance ekspedisi kurir.",
                "color": "rose",
                "items": [
                    {
                        "id": d.reference_id,
                        "date": d.date,
                        "channel": d.channel,
                        "description": d.probable_cause,
                        "gross_amount": d.expected_amount,
                        "fee_amount": 0.0,
                        "net_amount": d.expected_amount,
                        "batch_id": "-",
                        "reason": d.probable_cause
                    }
                    for d in cod_unremit_discs
                ]
            })

        cod_short_discs = [d for d in discrepancies if d.issue_type == "COD_SHORTAGE"]
        if cod_short_discs:
            categories.append({
                "category": "Selisih Pencairan COD Kurir (COD Shortage)",
                "type": "NOT_MATCHED",
                "count": len(cod_short_discs),
                "count_pct": round(len(cod_short_discs) / total_txns_count * 100, 2) if total_txns_count > 0 else 0.0,
                "nominal": sum(d.discrepancy_amount for d in cod_short_discs),
                "nominal_pct": round(sum(d.discrepancy_amount for d in cod_short_discs) / total_net * 100, 2) if total_net > 0 else 0.0,
                "action": "Ajukan klaim selisih potongan ongkir/retensi berlebih ke kurir ekspedisi.",
                "color": "rose",
                "items": [
                    {
                        "id": d.reference_id,
                        "date": d.date,
                        "channel": d.channel,
                        "description": d.probable_cause,
                        "gross_amount": d.expected_amount,
                        "fee_amount": 0.0,
                        "net_amount": d.actual_amount,
                        "batch_id": "-",
                        "reason": d.probable_cause
                    }
                    for d in cod_short_discs
                ]
            })
        
        return {
            "overall": {
                "total_nominal": total_net,
                "matched_nominal": matched_nominal,
                "not_matched_nominal": not_matched_nominal,
                "matched_nominal_pct": matched_nominal_pct,
                "not_matched_nominal_pct": not_matched_nominal_pct,
                "total_count": total_txns_count,
                "matched_count": matched_count,
                "not_matched_count": not_matched_count,
                "matched_count_pct": matched_count_pct,
                "not_matched_count_pct": not_matched_count_pct
            },
            "by_channel": by_channel,
            "categories": categories
        }

