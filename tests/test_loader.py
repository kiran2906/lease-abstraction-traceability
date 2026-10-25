from lease_trace.loader import html_to_text, load_lease_text


def test_html_table_rows_become_single_lines():
    html = "<html><body><p>Section 3.1 Base Rent.</p><table><tr><td>Year 1</td><td>$120,000.00</td></tr></table></body></html>"
    text = html_to_text(html)
    assert "Year 1 | $120,000.00" in text
    assert "Section 3.1 Base Rent." in text


def test_scripts_are_dropped():
    assert "alert" not in html_to_text("<html><script>alert(1)</script><p>Hello lease</p></html>")


def test_plain_text_is_cleaned():
    assert load_lease_text("tests/fixtures/sample_lease.txt").startswith("OFFICE LEASE AGREEMENT")


def _make_pdf(path, pages):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    for lines in pages:
        y = 740
        for line in lines:
            c.drawString(72, y, line)
            y -= 16
        c.showPage()
    c.save()


def test_text_pdf_is_extracted_page_by_page(tmp_path):
    from lease_trace.loader import load_pdf_pages

    f = tmp_path / "lease.pdf"
    body = ["Section 2.1 Commencement Date. The term of this Lease shall commence on March 1, 2024."] * 3
    _make_pdf(f, [body, ["Section 3.1 Base Rent. Year 1 | $120,000.00 | $10,000.00"] * 3])
    pages = load_pdf_pages(f)
    assert len(pages) == 2
    assert "commence on March 1, 2024" in pages[0]
    assert "$120,000.00" in pages[1]
    text = load_lease_text(f)
    assert "commence on March 1, 2024" in text and "$120,000.00" in text


def test_pdf_detected_by_content_not_just_extension(tmp_path):
    f = tmp_path / "lease.bin"
    _make_pdf(f, [["Section 2.1 Commencement Date. The term shall commence on March 1, 2024 and run five years."] * 3])
    assert "commence on March 1, 2024" in load_lease_text(f)


def test_scanned_pdf_is_refused_with_ocr_message(tmp_path):
    f = tmp_path / "scan.pdf"
    _make_pdf(f, [[], []])  # pages with no text layer
    try:
        load_lease_text(f)
    except ValueError as e:
        assert "scanned" in str(e) and "OCR" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_corrupt_pdf_gives_clear_error(tmp_path):
    f = tmp_path / "bad.pdf"
    f.write_bytes(b"%PDF-1.4 not really a pdf")
    try:
        load_lease_text(f)
    except ValueError as e:
        assert "could not read PDF" in str(e)
    else:
        raise AssertionError("expected ValueError")
