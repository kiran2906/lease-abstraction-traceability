"""Field definitions. Phase 1 runs only DEFAULT_FIELDS; the rest are ready for later."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    name: str
    definition: str
    normalized_format: str


FIELDS = {
    "commencement_date": FieldSpec(
        "commencement_date",
        "The date the lease term commences (the 'Commencement Date'). Not the date the lease was signed, "
        "and not the rent commencement date unless the lease treats them as the same.",
        '{"date": "YYYY-MM-DD" or null, "basis": "explicit_date" | "event_based" | "not_stated"}. '
        "Use basis event_based with date null when the Commencement Date is defined by an event "
        "(for example delivery of the premises or completion of work) and no calendar date is stated.",
    ),
    "expiration_date": FieldSpec(
        "expiration_date",
        "The date the initial lease term expires, or the length of the initial term if no date is stated.",
        '{"date": "YYYY-MM-DD" or null, "basis": "explicit_date" | "term_only" | "event_based" | "not_stated", '
        '"term_months": integer or null}. Use term_only when only a length is stated; do not compute a date.',
    ),
    "base_rent_schedule": FieldSpec(
        "base_rent_schedule",
        "The scheduled base (minimum) rent for the initial term: each rent period with its amount. "
        "Exclude additional rent, operating expense or tax pass-throughs, and security deposits.",
        '{"schedule": [{"start": "YYYY-MM-DD" or null, "end": "YYYY-MM-DD" or null, "amount": number, '
        '"unit": "per_year" | "per_month" | "per_sf_per_year"}]}. Keep periods in lease order. Use null for '
        "start and end when the lease gives periods only as lease years or months with no calendar dates, "
        "and describe the period labels in notes. Report amounts in the unit the lease states.",
    ),
    "escalation_clause": FieldSpec(
        "escalation_clause",
        "How base rent increases over time, if at all.",
        '{"type": "fixed_percent" | "fixed_step" | "cpi" | "market_reset" | "none" | "other", '
        '"details": "short plain-language summary"}',
    ),
    "renewal_options": FieldSpec(
        "renewal_options",
        "Tenant or landlord options to extend the term.",
        '{"options": [{"count": integer or null, "term_months": integer or null, '
        '"notice_days": integer or null, "rent_basis": string or null}]}',
    ),
    "termination_rights": FieldSpec(
        "termination_rights",
        "Rights of either party to terminate the lease early, other than for default.",
        '{"rights": [{"party": "tenant" | "landlord" | "mutual", "trigger": string, '
        '"notice_days": integer or null, "fee": string or null}]}',
    ),
}

DEFAULT_FIELDS = ["commencement_date", "base_rent_schedule"]
