import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import rotaeno
from rotaoff import data
tt = rotaeno.api.taptap
prof = __import__('rotaoff.store', fromlist=['x']).require_ready_profile()
region = tt.ServerRegion.CN if prof["serverCode"] == "cn" else tt.ServerRegion.GLOBAL
api = tt.__dict__
import rotaeno.api.taptap_processor as tp
client = tp.TapTapAPI(region=region, user_profile=prof)
raw = client.get_cloud_save(add_to_database=False, raw_data=None) if False else None
songs = (client.get_user_data(raw_data=None) if False else None)
# 直接从 cloud save 拿原始
save = client.get_cloud_save(add_to_database=False)
