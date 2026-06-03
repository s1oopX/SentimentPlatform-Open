import csv
import json

from ml_assets.workspace.evaluation.serialization import sanitize_for_json


def save_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(sanitize_for_json(payload), file, ensure_ascii=False, indent=2)


def save_csv(path, rows):
    rows = [sanitize_for_json(row) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as file:
            file.write("")
        return

    fieldnames = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

