from types import SimpleNamespace

from lease_trace.extract import build_tool, extract_lease
from lease_trace.loader import load_lease_text

LEASE = load_lease_text("tests/fixtures/sample_lease.txt")


class FakeClient:
    """Stands in for anthropic.Anthropic so no API key or network is needed."""

    def __init__(self, results):
        self.messages = SimpleNamespace(create=lambda **kw: self._create(**kw))
        self._results = results
        self.last_kwargs = None

    def _create(self, **kwargs):
        self.last_kwargs = kwargs
        block = SimpleNamespace(type="tool_use", input={"results": self._results})
        return SimpleNamespace(content=[block])


def _found(field, quote, conf=0.95, normalized=None):
    return {
        "field": field, "status": "found", "normalized": normalized or {"x": 1},
        "evidence": [{"clause_ref": "Section 2.1", "quote": quote}], "confidence": conf,
    }


def test_verified_high_confidence_is_auto_accepted():
    c = FakeClient([_found("commencement_date", "The term of this Lease shall commence on March 1, 2024")])
    rec = extract_lease(c, "l1", LEASE, ["commencement_date"])[0]
    assert rec["status"] == "auto_accepted"
    assert rec["evidence"][0]["quote_verified"] is True


def test_verified_low_confidence_goes_to_review():
    c = FakeClient([_found("commencement_date", "The term of this Lease shall commence on March 1, 2024", conf=0.5)])
    assert extract_lease(c, "l1", LEASE, ["commencement_date"])[0]["status"] == "needs_review"


def test_fabricated_quote_is_rejected_even_with_high_confidence():
    c = FakeClient([_found("commencement_date", "The term shall begin on June 1, 2024 exactly", conf=0.99)])
    rec = extract_lease(c, "l1", LEASE, ["commencement_date"])[0]
    assert rec["status"] == "quote_check_failed"
    assert "not_in_source" in rec["notes"]


def test_found_without_evidence_is_rejected():
    item = {"field": "commencement_date", "status": "found", "normalized": {"date": "2024-03-01"},
            "evidence": [], "confidence": 0.9}
    rec = extract_lease(FakeClient([item]), "l1", LEASE, ["commencement_date"])[0]
    assert rec["status"] == "quote_check_failed"


def test_missing_field_becomes_not_found():
    rec = extract_lease(FakeClient([]), "l1", LEASE, ["base_rent_schedule"])[0]
    assert rec["status"] == "not_found"


def test_tool_is_forced_and_enum_matches_requested_fields():
    c = FakeClient([])
    extract_lease(c, "l1", LEASE, ["commencement_date"])
    assert c.last_kwargs["tool_choice"]["type"] == "tool"
    enum = build_tool(["commencement_date"])["input_schema"]["properties"]["results"]["items"]["properties"]["field"]["enum"]
    assert enum == ["commencement_date"]


def test_oversized_lease_is_refused_not_truncated():
    try:
        extract_lease(FakeClient([]), "big", "x" * 500_000, ["commencement_date"])
    except ValueError as e:
        assert "exceeds" in str(e)
    else:
        raise AssertionError("expected ValueError")
