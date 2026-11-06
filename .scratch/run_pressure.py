import os
import subprocess
import sys
import time

OUT = os.path.join(".scratch", "pressure2_stdout.txt")
ERR = os.path.join(".scratch", "pressure2_stderr.txt")
DURATION = 60

cmd = [sys.executable, "run_tasks.py", "--filter", "i % 6 == 0", "--interval", "5"]
started = time.time()
with open(OUT, "w", encoding="utf-8") as out, open(ERR, "w", encoding="utf-8") as err:
    process = subprocess.Popen(cmd, stdout=out, stderr=err)
    time.sleep(DURATION)
    process.terminate()
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
print(f"duration={time.time() - started:.1f}s returncode={process.returncode}")