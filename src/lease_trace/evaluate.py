"""Scoring: compare extracted records against hand-made labels."""
from __future__ import annotations

from collections import defaultdict

DATE_FIELDS = {"commencement_date", "expiration_date"}
SCORABLE_FIELDS = DATE_FIELDS | {"base_rent_schedule"}


def _schedule_key(normalized):
    out = []
    for item in (normalized or {}).get("schedule") or []:
        try:
            amount = round(float(item["amount"]), 2) if item.get("amount") is not None else None
        except (TypeError, ValueError):
            amount = None
        out.append((item.get("start"), item.get("end"), amount, item.get("unit")))
    return out


def values_match(field: str, predicted, expected) -> bool:
    predicted = predicted or {}
    expected = expected or {}
    if field in DATE_FIELDS:
        keys = [k for k in ("date", "basis", "term_months") if k in expected]
        return all(predicted.get(k) == expected.get(k) for k in keys)
    if field == "base_rent_schedule":
        return _schedule_key(predicted) == _schedule_key(expected)
    raise NotImplementedError(f"No automatic comparator for {field}")


def score_record(field: str, record: dict, label: dict) -> dict:
    """Three separate questions: right value? verified citation? both?"""
    status = record["status"]
    if label["status"] == "not_found":
        correct = status == "not_found"
        return {"value_correct": correct, "citation_verified": correct, "correct_and_cited": correct}
    if status == "not_found":
        return {"value_correct": False, "citation_verified": False, "correct_and_cited": False}
    value_ok = values_match(field, record.get("normalized"), label.get("normalized"))
    cited = status != "quote_check_failed"
    return {"value_correct": value_ok, "citation_verified": cited, "correct_and_cited": value_ok and cited}


def summarize(scored_rows):
    """scored_rows: iterable of (split, field, score_dict). Returns {(split, field): {...}}."""
    acc = defaultdict(lambda: {"n": 0, "value_correct": 0, "citation_verified": 0, "correct_and_cited": 0})
    for split, field, s in scored_rows:
        a = acc[(split, field)]
        a["n"] += 1
        for k in ("value_correct", "citation_verified", "correct_and_cited"):
            a[k] += int(s[k])
    return dict(acc)


def to_markdown(summary) -> str:
    lines = [
        "| Split | Field | Leases | Value correct | Citation verified | Correct and cited |",
        "|---|---|---|---|---|---|",
    ]
    for (split, field), a in sorted(summary.items()):
        n = a["n"]
        pct = lambda x: f"{x}/{n} ({100 * x / n:.0f}%)"
        lines.append(
            f"| {split} | {field} | {n} | {pct(a['value_correct'])} | "
            f"{pct(a['citation_verified'])} | {pct(a['correct_and_cited'])} |"
        )
    return "\n".join(lines)
