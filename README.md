# lease-abstraction-traceability

Lease abstraction where **every extracted field must point to verbatim contract text**. If the model's supporting quote can't be found in the lease, the field is rejected, no matter how confident the model sounds.

Built for compliance and reconciliation work: a reviewer should be able to prove where any number in a system came from.

## Status

| Phase | Scope | State |
|---|---|---|
| 1 | Single-pass extractor, verbatim-quote check, eval harness (commencement date, base rent) | In progress |
| 2 | Remaining fields (expiration, escalation, renewal, termination) | Planned |
| 3 | LangGraph orchestration around the measured extractor | Planned |
| 4 | Review UI with highlighted source passage | Planned |
| 5 | Reconciliation against a TRIRIGA-shaped system of record and a ledger | Planned |

## Results

_No results yet. Fill this in from `evals/results/` after running the held-out split._

| Field | Leases (held-out) | Value correct | Citation verified | Correct and cited |
|---|---|---|---|---|
| commencement_date | | | | |
| base_rent_schedule | | | | |

## How it works

1. `loader` converts an EDGAR HTML, plain text, or text-based PDF lease to clean text (HTML table rows become `a | b | c` lines).
2. `extract` sends the whole lease to the model once, with a forced tool call that returns, per field: status, normalized value, evidence quotes, confidence.
3. `verify` checks each quote against the lease text (whitespace and punctuation normalised). No match means status `quote_check_failed`.
4. Remaining statuses: `auto_accepted` (verified, confidence >= 0.85), `needs_review` (verified, lower confidence), `not_found` (the model says the lease doesn't state it).
5. `evals/run_eval.py` scores against hand-made labels and reports three numbers separately: value correct, citation verified, and both.

### Design decisions
- **`not_found` is a valid answer**, so the model isn't pushed to invent values.
- **Confidence is self-reported by the model.** Treat it as a weak signal until you have checked it against your labels.
- **No agents, retrieval, or chunking in v1.** Add them when the eval shows a concrete need. Leases over 400k characters are refused, not truncated.
- **Public data only.** Test leases come from SEC EDGAR. Do not put employer or client documents in this repo.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=...        # needed only for real extraction
pytest                              # offline tests, no API calls

# 1. Put a lease (.htm, .txt or text-based .pdf) in data/raw/, then check what the model will see
python -m lease_trace.loader data/raw/my_lease.htm

# 2. Extract one lease
python -m lease_trace.extract data/raw/my_lease.htm --out outputs/my_lease.json

# 3. Label leases (see docs/labeling_guide.md), then score
python evals/run_eval.py --split tune
```

The model name defaults to `claude-sonnet-5-5`. Override it with `LEASE_MODEL` or `--model`.

## Layout

```
src/lease_trace/   loader, fields, extract, verify, evaluate
evals/             run_eval.py and saved result tables
data/labels/       hand-made answer keys (committed)
data/raw/          downloaded leases (not committed; list them in data/SOURCES.md)
docs/              labeling guide
tests/             offline tests using a fake client
```

## Limitations
- Reads HTML, plain text, and text-based PDFs. Scanned PDFs (no selectable text) are refused with a clear message; OCR is not supported yet.
- PDF text extraction can garble multi-column layouts and tables, and repeated page headers/footers land mid-text, so a quote that spans a page break may fail verification. Always check the loader output before labeling.
- Page numbers are kept internally (`load_pdf_pages`) but are not yet in the output records; page and bounding-box citations arrive with the review UI.
- Automatic scoring exists for dates and base rent only; other fields need comparators.
- Strict matching: a rent schedule is correct only if every period, amount, and unit matches.
