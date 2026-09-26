# generate_submission.py
"""Generate the required `submission.jsonl` file.

The challenge expects 30 lines, each containing the output of ``compose`` for a
specific (category, merchant, trigger) pair.  This script loads the provided
dataset, selects the first 30 triggers (or a random sample if there are more),
matches each trigger to its merchant, loads the corresponding category, and
writes the bot's response to ``submission.jsonl``.

The script assumes the environment variable ``GOOGLE_AI_API_KEY`` is set so that
the Gemini client in ``src.bot`` can run deterministically (temperature=0).
"""
import os
import json
import random
from pathlib import Path

# Import the compose function from the package
from src.bot import compose

DATA_ROOT = Path(__file__).parent / "dataset"

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def main(sample_size: int = 30, output_path: Path = Path("submission.jsonl")):
    # Load all triggers
    trigger_files = list((DATA_ROOT / "triggers").glob("*.json"))
    if len(trigger_files) == 0:
        raise RuntimeError("No trigger files found in dataset/triggers")
    # Randomly sample (or take first) triggers
    random.seed(0)  # deterministic sampling
    selected_triggers = random.sample(trigger_files, min(sample_size, len(trigger_files)))

    lines = []
    for idx, trigger_path in enumerate(selected_triggers, start=1):
        trigger = load_json(trigger_path)
        merchant_id = trigger["payload"].get("merchant_id")
        if not merchant_id:
            # Some triggers may not have a merchant_id (unlikely); skip
            continue
        # Load merchant JSON
        merchant_path = next((DATA_ROOT / "merchants").glob(f"{merchant_id}.json"), None)
        if merchant_path is None:
            # fallback: search by prefix
            merchant_path = next((DATA_ROOT / "merchants").glob(f"*{merchant_id}*.json"), None)
        if merchant_path is None:
            raise RuntimeError(f"Merchant file for id {merchant_id} not found")
        merchant = load_json(merchant_path)

        # Load category based on merchant's category slug (assumed present in merchant['category_slug'] or similar)
        # The dataset stores the category slug inside the merchant JSON under the key "category_slug"
        category_slug = merchant.get("category_slug") or merchant.get("slug")
        if not category_slug:
            raise RuntimeError(f"Category slug not found in merchant {merchant_path.name}")
        category_path = Path(__file__).parent / f"dataset/categories/{category_slug}.json"
        if not category_path.is_file():
            raise RuntimeError(f"Category file {category_slug}.json not found")
        category = load_json(category_path)

        # Some triggers are customer‑facing; try to load a customer if payload contains "customer_id"
        customer = None
        cust_id = trigger["payload"].get("customer_id")
        if cust_id:
            cust_path = next((DATA_ROOT / "customers").glob(f"*{cust_id}*.json"), None)
            if cust_path:
                customer = load_json(cust_path)

        # Call the bot
        result = compose(
            category=category,
            merchant=merchant,
            trigger=trigger,
            customer=customer,
        )
        # Build the JSONL line – include a test_id for reference
        line = {
            "test_id": f"T{idx:02d}",
            **result,
        }
        lines.append(line)

    # Write to file
    with output_path.open("w", encoding="utf-8") as f:
        for line in lines:
            json.dump(line, f)
            f.write("\n")
    print(f"Wrote {len(lines)} submissions to {output_path}")

if __name__ == "__main__":
    main()
