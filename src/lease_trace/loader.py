"""Turn a lease file (EDGAR HTML, plain text, or text-based PDF) into clean text.

Scanned PDFs (images with no text layer) are detected and refused with a clear
message; they need OCR, which this project does not do yet.
Run `python -m lease_trace.loader FILE` to see exactly the text the model
receives. Copy label quotes from that output.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

_BLOCK_TAGS = ["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"]


def clean_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n ", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    # One line per table row, cells joined with " | ", so rent tables stay readable.
    for tr in soup.find_all("tr"):
        if tr.find("table"):
            continue
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        tr.replace_with(soup.new_string(" | ".join(cells) + "\n"))
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all(_BLOCK_TAGS):
        tag.append("\n")
    return clean_text(soup.get_text(""))


MIN_CHARS_PER_PAGE = 100  # below this on average, the PDF is almost certainly a scan


def _is_pdf(p: Path) -> bool:
    if p.suffix.lower() == ".pdf":
        return True
    with open(p, "rb") as fh:
        return fh.read(5) == b"%PDF-"


def load_pdf_pages(path) -> list[str]:
    """Return cleaned text per page. Page order is preserved so page numbers
    can be used for citations later."""
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError(f"{path}: PDF is password-protected.")
        pages = [clean_text(page.extract_text() or "") for page in reader.pages]
    except PyPdfError as e:
        raise ValueError(f"{path}: could not read PDF ({e}).") from e

    if not pages:
        raise ValueError(f"{path}: PDF has no pages.")
    total = sum(len(t) for t in pages)
    if total < MIN_CHARS_PER_PAGE * len(pages):
        raise ValueError(
            f"{path}: only {total} characters of text found across {len(pages)} page(s). "
            "This looks like a scanned PDF with no text layer. OCR is not supported yet; "
            "use a text-based PDF, or an EDGAR HTML/text exhibit."
        )
    return pages


def load_lease_text(path) -> str:
    p = Path(path)
    if _is_pdf(p):
        return clean_text("\n\n".join(load_pdf_pages(p)))
    raw = p.read_text(encoding="utf-8", errors="replace")
    if p.suffix.lower() in {".htm", ".html"} or "<html" in raw[:5000].lower():
        return html_to_text(raw)
    return clean_text(raw)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m lease_trace.loader FILE")
    try:
        print(load_lease_text(sys.argv[1]))
    except ValueError as e:
        sys.exit(f"error: {e}")
