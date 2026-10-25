# Labeling guide

Your labels are the answer key. Inconsistent labels produce meaningless accuracy numbers, so follow these rules every time.

## Steps
1. Download a lease (EDGAR `.htm`/`.txt`, or a text-based `.pdf`) into `data/raw/` and add a row to `data/SOURCES.md`.
2. Run `python -m lease_trace.loader data/raw/<file>` and read the text the model will see.
3. Copy `data/labels/_template.json` to `data/labels/<lease_id>.json` and fill it in.
4. Copy every `quote` from the loader output, not from the original document, so it can be verified. `run_eval.py` warns when a label quote isn't found.

## Splits
- `tune`: leases you look at while improving prompts and field definitions.
- `heldout`: leases you never look at while tuning. Keep at least 3 before you quote any number publicly.
- If you change the prompt after seeing held-out results, relabel those leases as `tune` and bring in fresh held-out ones.

## Conventions
- **commencement_date:** use `explicit_date` only when a calendar date is stated. If it is defined by an event (delivery, completion of work) with no date, use `event_based` and `"date": null`. Not the signing date.
- **base_rent_schedule:** initial term only. Exclude operating expenses, taxes, and deposits. Keep the amount and unit exactly as the lease states them (do not convert monthly to annual). Use `null` start/end when the lease only says "Lease Year N".
- **Amendments:** if an amendment in the same file changes a term, label the controlling (latest) term.
- **not_found:** use it only when the lease truly doesn't state the field.
- **Ambiguous cases:** pick the most defensible reading, and write the reasoning in a `"label_notes"` key so you can revisit it.
