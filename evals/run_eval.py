"""Run the extractor over labeled leases and report accuracy.

Defaults to the `tune` split. Look at `heldout` rarely, and never change the
prompt after seeing held-out results (if you do, those leases become `tune`
and you need fresh held-out ones).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lease_trace.evaluate import SCORABLE_FIELDS, score_record, summarize, to_markdown
from lease_trace.extract import DEFAULT_MODEL, extract_lease, extractor_version
from lease_trace.loader import load_lease_text
from lease_trace.verify import normalize, verify_quote

from dotenv import load_dotenv

_ = load_dotenv(override=True)

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "data" / "labels"
OUTPUTS = ROOT / "outputs"
RESULTS = ROOT / "evals" / "results"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--split", choices=["tune", "heldout", "all"], default="tune")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument(
        "--no-extract",
        action="store_true",
        help="Score cached outputs only; make no API calls",
    )
    args = p.parse_args()

    if args.split in ("heldout", "all"):
        print(
            "NOTE: do not change prompts or field definitions based on held-out results.\n",
            file=sys.stderr,
        )

    version = extractor_version(args.model)
    cache_dir = OUTPUTS / version.replace("+", "_")
    client = None
    scored = []

    for label_path in sorted(LABELS.glob("*.json")):
        if label_path.name.startswith("_"):
            continue
        label = json.loads(label_path.read_text())
        split = label.get("split", "tune")
        if args.split != "all" and split != args.split:
            continue
        lease_id = label["lease_id"]
        fields = [f for f in label["fields"] if f in SCORABLE_FIELDS]
        skipped = [f for f in label["fields"] if f not in SCORABLE_FIELDS]
        if skipped:
            print(
                f"{lease_id}: no automatic comparator yet for {', '.join(skipped)} (skipped)",
                file=sys.stderr,
            )

        text = load_lease_text(ROOT / label["source_file"])
        # print(f"{ROOT} / {label['source_file']}")
        source_norm = normalize(text)
        for f, lab in label["fields"].items():  # catch labeling typos
            if (
                lab.get("status") == "found"
                and lab.get("quote")
                and not verify_quote(lab["quote"], source_norm)[0]
            ):
                print(
                    f"WARNING {lease_id}/{f}: label quote not found in source text",
                    file=sys.stderr,
                )

        cache = cache_dir / f"{lease_id}.json"
        records = json.loads(cache.read_text()) if cache.exists() else []
        if {r["field"] for r in records} < set(fields):
            if args.no_extract:
                print(f"{lease_id}: no cached output, skipping", file=sys.stderr)
                continue
            if client is None:
                import anthropic

                client = anthropic.Anthropic()
            records = extract_lease(client, lease_id, text, fields, args.model)
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(records, indent=2))

        by_field = {r["field"]: r for r in records}
        for f in fields:
            scored.append((split, f, score_record(f, by_field[f], label["fields"][f])))

    if not scored:
        sys.exit(
            "No labeled leases matched. Add labels to data/labels/ (see docs/labeling_guide.md)."
        )

    table = to_markdown(summarize(scored))
    print(f"\nExtractor: {version}\n\n{table}")
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"{version.replace('+', '_')}_{args.split}.md"
    out.write_text(f"Extractor: {version}\n\n{table}\n")
    print(f"\nSaved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
