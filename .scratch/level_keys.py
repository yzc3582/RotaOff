import sys, json, collections
sys.stdout.reconfigure(encoding='utf-8')
import rotaeno
from rotaoff import data
snap = data.fetch_snapshot(record_history=False)
counts = collections.Counter()
for item in snap["songDatas"]:
    counts[item.get("level")] += 1
print("level keys:", dict(counts))
print("noise lines:", len([l for l in (data.fetch_snapshot.last_noise or "").splitlines() if l]))
print("diff==0 charts:", len(data.charts_without_diff(snap["songDatas"])))
