"""RotaOff 兼容启动器。

原来的 bot.py 是 Discord 机器人：消息回调里跑一次查询，再回一张图。
现在所有逻辑都在 rotaoff/ 里，这个文件只负责把人领进交互界面：

    python bot.py            # 等同 python tui.py

自动化（不交互）请用：
    python run_tasks.py --task 1 --interval 300
"""

import sys

from rotaoff import ui
from rotaoff.store import RotaOffError
from tui import main

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except RotaOffError as error:
        ui.error(str(error))
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        sys.exit(130)
