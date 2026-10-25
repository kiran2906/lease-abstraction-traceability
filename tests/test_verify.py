from lease_trace.verify import normalize, verify_quote

SOURCE = normalize(open("tests/fixtures/sample_lease.txt").read())


def test_exact_quote_verifies_and_reports_offsets():
    q = 'The term of this Lease shall commence on March 1, 2024'
    ok, start, end, reason = verify_quote(q, SOURCE)
    assert ok and reason is None
    assert SOURCE[start:end] == normalize(q)


def test_whitespace_and_curly_quotes_are_tolerated():
    q = "This Office Lease Agreement (this \u201cLease\u201d)   is made\nas of January 15, 2024"
    assert verify_quote(q, SOURCE)[0]


def test_fabricated_quote_fails():
    ok, _, _, reason = verify_quote("The term of this Lease shall commence on April 1, 2024", SOURCE)
    assert not ok and reason == "not_in_source"


def test_ellipsis_stitching_fails():
    ok, _, _, reason = verify_quote("The term of this Lease shall commence ... and shall expire on February 28, 2029", SOURCE)
    assert not ok and reason == "not_in_source"


def test_too_short_and_too_long_are_rejected():
    assert verify_quote("Lease", SOURCE)[3] == "too_short"
    assert verify_quote("a" * 2000, SOURCE)[3] == "too_long"
