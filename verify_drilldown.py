"""
verify_drilldown.py
-------------------
Memverifikasi data drill-down kategori match vs not match.
"""

from starlette.testclient import TestClient
from main import app

client = TestClient(app)
res = client.get('/api/demo')
assert res.status_code == 200
data = res.json()
cats = data['data']['match_analytics']['categories']

print("[OK] STATUS DRILL-DOWN PER KATEGORI:")
for c in cats:
    print(f"\n* Kategori: {c['category']} (Total: {c['count']} item)")
    for itm in c.get('items', []):
        print(f"   -> [{itm['channel']}] ID: {itm['id']} | Tgl: {itm['date']} | Gross: Rp {itm['gross_amount']:,.0f} | Net: Rp {itm['net_amount']:,.0f} | Batch: {itm['batch_id']}")
        print(f"      Alasan: {itm['reason']}")
