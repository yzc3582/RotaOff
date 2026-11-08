import contextlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rotaoff import lock, select, store, tasks

all_tasks = store.load_tasks()
selected = select.apply_selection(all_tasks, [("filter", "i % 5 == 0")])
print(f"selected={len(selected)}", file=sys.stderr)

lock.acquire("automation")
try:
    with open(".scratch/pressure3_stdout.txt", "w", encoding="utf-8") as out, \
            open(".scratch/pressure3_stderr.txt", "w", encoding="utf-8") as err:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            for index in range(1, 9):
                print(f"round {index} start", file=sys.stderr)
                failures = 0
                for result in tasks.run_tasks(selected):
                    if not result.get("ok"):
                        failures += 1
                print(f"round {index} end failures={failures}", file=sys.stderr)
                if index < 8:
                    time.sleep(5)
finally:
    lock.release()

print("done", file=sys.stderr)