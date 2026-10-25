"""Single-pass extraction with evidence, then verbatim verification.

v1 deliberately has no agents, no retrieval and no chunking: the whole lease
goes to the model once and the result is checked. Add structure only when the
eval numbers show you need it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .fields import DEFAULT_FIELDS, FIELDS
from .loader import load_lease_text
from .verify import normalize, verify_quote

PROMPT_VERSION = "v1"
DEFAULT_MODEL = os.environ.get("LEASE_MODEL", "claude-sonnet-5-5")
AUTO_ACCEPT_THRESHOLD = 0.85
MAX_CHARS = 400_000
TOOL_NAME = "record_lease_fields"

SYSTEM_PROMPT = """You extract structured facts from commercial lease agreements for a compliance review team. Every fact you report must be traceable to the document.

Rules:
1. Use only the lease text provided. Never use outside knowledge or assumptions.
2. For every field you report as found, provide one or more evidence items. Each evidence quote must be copied exactly, character for character, from the lease text as one contiguous passage. Do not use ellipses, do not paraphrase, and do not stitch separate passages into one quote (use separate evidence items instead).
3. Keep each quote as short as possible while still supporting the value, usually one to three sentences or one table row.
4. If the lease does not state the field, or you cannot find supporting text, return status "not_found" with an empty normalized object and no evidence. Reporting not_found is correct and preferred over guessing.
5. If an amendment or exhibit in the text changes a term, report the controlling (latest) term and cite both passages.
6. Do not do date arithmetic or compute values the lease does not state, unless the field definition says to.
7. confidence is your own estimate from 0 to 1 that the normalized value is correct and fully supported. Use below 0.6 when the text is ambiguous.
8. clause_ref is the section or article label as it appears in the lease (for example "Section 4.2(a)"), or "unknown" if none is visible."""


def extractor_version(model: str) -> str:
    return f"{PROMPT_VERSION}+{model}"


def build_tool(field_names):
    evidence_item = {
        "type": "object",
        "properties": {"clause_ref": {"type": "string"}, "quote": {"type": "string"}},
        "required": ["clause_ref", "quote"],
    }
    result_item = {
        "type": "object",
        "properties": {
            "field": {"type": "string", "enum": list(field_names)},
            "status": {"type": "string", "enum": ["found", "not_found"]},
            "normalized": {
                "type": "object",
                "description": "Value in the format given for this field. Empty object if not_found.",
            },
            "evidence": {"type": "array", "items": evidence_item},
            "confidence": {"type": "number"},
            "notes": {"type": "string"},
        },
        "required": ["field", "status", "normalized", "evidence", "confidence"],
    }
    return {
        "name": TOOL_NAME,
        "description": "Record the extracted lease fields with verbatim evidence.",
        "input_schema": {
            "type": "object",
            "properties": {"results": {"type": "array", "items": result_item}},
            "required": ["results"],
        },
    }


def build_user_prompt(lease_text: str, field_names) -> str:
    lines = ["Extract the following fields. Return exactly one result per field.", ""]
    for name in field_names:
        spec = FIELDS[name]
        lines.append(f"Field: {spec.name}")
        lines.append(f"Definition: {spec.definition}")
        lines.append(f"Normalized format: {spec.normalized_format}")
        lines.append("")
    lines.append("<lease>")
    lines.append(lease_text)
    lines.append("</lease>")
    return "\n".join(lines)


def _create(client, model, lease_text, field_names, tool_choice, nudge=""):
    return client.messages.create(
        model=model,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        tools=[build_tool(field_names)],
        tool_choice=tool_choice,
        messages=[
            {
                "role": "user",
                "content": build_user_prompt(lease_text, field_names) + nudge,
            }
        ],
    )


def call_model(client, model: str, lease_text: str, field_names):
    # Only one tool is defined, so {"type": "any"} forces it without naming it.
    # If the API rejects tool_choice for this model, fall back to "auto" with an explicit instruction.
    try:
        resp = _create(client, model, lease_text, field_names, {"type": "any"})
    except Exception as e:
        if getattr(e, "status_code", None) == 400 and "tool_choice" in str(e):
            nudge = f"\n\nRespond only by calling the {TOOL_NAME} tool."
            resp = _create(
                client, model, lease_text, field_names, {"type": "auto"}, nudge
            )
        else:
            raise
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input.get("results", [])
    raise RuntimeError("Model did not return a tool_use block.")


def _confidence(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def build_records(
    lease_id: str, source_norm: str, raw_results, field_names, model: str
):
    by_field = {}
    for item in raw_results or []:
        if isinstance(item, dict) and item.get("field") in field_names:
            by_field.setdefault(item["field"], item)

    now = datetime.now(timezone.utc).isoformat()
    records = []
    for name in field_names:
        item = by_field.get(name)
        rec = {
            "lease_id": lease_id,
            "field": name,
            "normalized": {},
            "evidence": [],
            "confidence": 0.0,
            "status": "not_found",
            "notes": "",
            "reviewer": None,
            "extractor_version": extractor_version(model),
            "model": model,
            "extracted_at": now,
        }
        if item is None:
            rec["notes"] = "Model returned no result for this field."
        elif item.get("status") != "found":
            rec["notes"] = item.get("notes", "")
        else:
            rec["normalized"] = item.get("normalized") or {}
            rec["confidence"] = _confidence(item.get("confidence"))
            rec["notes"] = item.get("notes", "")
            problems = []
            for ev in item.get("evidence") or []:
                ok, start, end, reason = verify_quote(ev.get("quote", ""), source_norm)
                rec["evidence"].append(
                    {
                        "clause_ref": ev.get("clause_ref", "unknown"),
                        "quote": ev.get("quote", ""),
                        "quote_verified": ok,
                        "char_start": start,
                        "char_end": end,
                    }
                )
                if not ok:
                    problems.append(reason)
            if not rec["evidence"]:
                problems.append("no_evidence")
            if problems:
                rec["status"] = "quote_check_failed"
                rec["notes"] = (
                    rec["notes"] + f" [verification: {', '.join(problems)}]"
                ).strip()
            elif rec["confidence"] >= AUTO_ACCEPT_THRESHOLD:
                rec["status"] = "auto_accepted"
            else:
                rec["status"] = "needs_review"
        records.append(rec)
    return records


def extract_lease(
    client, lease_id: str, lease_text: str, field_names, model: str = DEFAULT_MODEL
):
    if len(lease_text) > MAX_CHARS:
        raise ValueError(
            f"{lease_id}: {len(lease_text):,} characters exceeds the v1 single-pass limit of {MAX_CHARS:,}. "
            "Pick a shorter lease for now."
        )
    raw = call_model(client, model, lease_text, field_names)
    return build_records(lease_id, normalize(lease_text), raw, field_names, model)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Extract lease fields with verbatim evidence."
    )
    p.add_argument("lease_file")
    p.add_argument(
        "--fields", nargs="+", default=DEFAULT_FIELDS, choices=sorted(FIELDS)
    )
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--lease-id")
    p.add_argument("--out", help="Write JSON here instead of stdout")
    args = p.parse_args(argv)

    import anthropic  # imported here so the offline tests do not need it

    lease_id = args.lease_id or Path(args.lease_file).stem
    text = load_lease_text(args.lease_file)
    records = extract_lease(
        anthropic.Anthropic(), lease_id, text, args.fields, args.model
    )
    payload = json.dumps(records, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(payload)
    else:
        print(payload)
    for r in records:
        print(
            f"{r['field']}: {r['status']} (confidence {r['confidence']:.2f})",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
