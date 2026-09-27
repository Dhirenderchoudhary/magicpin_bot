"""Write submission.jsonl for the 30 canonical test pairs.

Uses dataset/expanded when present, otherwise the seed files.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.bot import compose

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "dataset"
EXPANDED = DATA / "expanded"
OUT = ROOT / "submission.jsonl"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _index(folder: Path, key: str) -> dict:
    found = {}
    if not folder.is_dir():
        return found
    for path in folder.glob("*.json"):
        row = _read(path)
        found[row.get(key) or path.stem] = row
    return found


def load_world():
    if (EXPANDED / "test_pairs.json").is_file():
        categories = _index(EXPANDED / "categories", "slug")
        merchants = _index(EXPANDED / "merchants", "merchant_id")
        customers = _index(EXPANDED / "customers", "customer_id")
        triggers = _index(EXPANDED / "triggers", "id")
        pairs = _read(EXPANDED / "test_pairs.json")["pairs"]
        return categories, merchants, customers, triggers, pairs

    categories = _index(DATA / "categories", "slug")
    merchants = {m["merchant_id"]: m for m in _read(DATA / "merchants_seed.json")["merchants"]}
    customers = {c["customer_id"]: c for c in _read(DATA / "customers_seed.json")["customers"]}
    trigger_rows = _read(DATA / "triggers_seed.json")["triggers"]
    triggers = {t["id"]: t for t in trigger_rows}
    pairs = [
        {
            "test_id": f"T{i:02d}",
            "trigger_id": trigger["id"],
            "merchant_id": trigger["merchant_id"],
            "customer_id": trigger.get("customer_id"),
        }
        for i, trigger in enumerate(trigger_rows, start=1)
    ]
    return categories, merchants, customers, triggers, pairs


def main() -> None:
    categories, merchants, customers, triggers, pairs = load_world()
    lines = []
    for pair in pairs[:30]:
        trigger = triggers[pair["trigger_id"]]
        merchant = merchants[pair["merchant_id"]]
        category = categories[merchant["category_slug"]]
        customer = customers.get(pair.get("customer_id")) if pair.get("customer_id") else None
        result = compose(category, merchant, trigger, customer)
        lines.append({"test_id": pair["test_id"], **result})

    with OUT.open("w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(f"Wrote {len(lines)} lines to {OUT}")


if __name__ == "__main__":
    main()
