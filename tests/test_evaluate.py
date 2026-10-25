from lease_trace.evaluate import score_record, summarize, to_markdown, values_match


def test_date_match_uses_date_and_basis():
    exp = {"date": "2024-03-01", "basis": "explicit_date"}
    assert values_match("commencement_date", {"date": "2024-03-01", "basis": "explicit_date"}, exp)
    assert not values_match("commencement_date", {"date": "2024-03-02", "basis": "explicit_date"}, exp)
    assert not values_match("commencement_date", {"date": None, "basis": "event_based"}, exp)


def test_rent_schedule_order_and_amounts_matter():
    a = {"schedule": [{"start": None, "end": None, "amount": 120000, "unit": "per_year"},
                      {"start": None, "end": None, "amount": 123600.0, "unit": "per_year"}]}
    b = {"schedule": [{"start": None, "end": None, "amount": 120000.0, "unit": "per_year"},
                      {"start": None, "end": None, "amount": 123600, "unit": "per_year"}]}
    assert values_match("base_rent_schedule", a, b)
    swapped = {"schedule": list(reversed(b["schedule"]))}
    assert not values_match("base_rent_schedule", a, swapped)


def test_right_value_with_failed_citation_is_not_fully_correct():
    rec = {"status": "quote_check_failed", "normalized": {"date": "2024-03-01", "basis": "explicit_date"}}
    lab = {"status": "found", "normalized": {"date": "2024-03-01", "basis": "explicit_date"}}
    s = score_record("commencement_date", rec, lab)
    assert s == {"value_correct": True, "citation_verified": False, "correct_and_cited": False}


def test_expected_not_found():
    s = score_record("commencement_date", {"status": "not_found", "normalized": {}}, {"status": "not_found"})
    assert s["correct_and_cited"]
    s2 = score_record("commencement_date", {"status": "auto_accepted", "normalized": {"date": "2024-01-01"}}, {"status": "not_found"})
    assert not s2["value_correct"]


def test_summary_markdown():
    rows = [("tune", "commencement_date", {"value_correct": True, "citation_verified": True, "correct_and_cited": True}),
            ("tune", "commencement_date", {"value_correct": False, "citation_verified": True, "correct_and_cited": False})]
    md = to_markdown(summarize(rows))
    assert "1/2 (50%)" in md and "2/2 (100%)" in md
