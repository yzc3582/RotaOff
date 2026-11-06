import json
import os

PATH = os.path.join("data", "tasks.json")
with open(PATH, encoding="utf-8") as handle:
    config = json.load(handle)

templates = config["tasks"]
tasks = []
for index in range(1, 56):
    task = dict(templates[(index - 1) % len(templates)])
    task["name"] = f'压测-{index:02d}-{task["type"]}'
    task["limit"] = 5
    tasks.append(task)

config["tasks"] = tasks
with open(PATH, "w", encoding="utf-8") as handle:
    json.dump(config, handle, ensure_ascii=False, indent=4)
print(f"tasks={len(tasks)}")