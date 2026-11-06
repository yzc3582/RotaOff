"""验证 data/song_data.db 被 SQLAlchemy engine 持有时，os.replace 是否报 WinError 5。"""
import os
import shutil
import sys

sys.path.insert(0, '.')
from rotaoff import library                      # noqa: E402

src = os.path.join('data', 'song_data.db')
probe = os.path.join('data', '_probe.db')
tmp = probe + '.tmp'
shutil.copyfile(src, probe)


def try_replace(tag):
    with open(tmp, 'wb') as file:
        file.write(b'probe')
    try:
        os.replace(tmp, probe)
        print(f'{tag}: replace OK（没有锁）')
        shutil.copyfile(src, probe)              # 复原，继续下一步
    except OSError as exc:
        print(f'{tag}: 失败 {type(exc).__name__} winerror={getattr(exc, "winerror", "")} {exc}')


try_replace('没有任何实例')

instance = library.open_database(probe)
try_replace('engine 已创建、未查询')
library.activate(instance)                       # 变成“当前曲库”，模拟真实会话

with open(tmp, 'wb') as file:
    file.write(b'probe')
try:
    library._replace_database(tmp, probe)
    print('走 _replace_database（会先 dispose）: OK')
except Exception as exc:                         # noqa: BLE001
    print('走 _replace_database: 失败', type(exc).__name__, exc)
    shutil.copyfile(src, probe)

os.remove(probe)
print('清理完成')
