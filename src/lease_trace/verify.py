"""Verbatim-quote verification.

This is the core guardrail of the project: a field only counts if the quote
that supports it can be found, character for character (after whitespace and
punctuation normalisation), in the lease text we actually gave the model.
"""
from __future__ import annotations

import re
import unicodedata

MIN_QUOTE_CHARS = 10
MAX_QUOTE_CHARS = 1500

_TRANSLATE = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
    }
)


def normalize(text: str) -> str:
    """Collapse whitespace and unify typographic punctuation.

    Offsets reported by verify_quote refer to this normalised text, not to the
    raw file.
    """
    text = unicodedata.normalize("NFKC", text).translate(_TRANSLATE)
    return re.sub(r"\s+", " ", text).strip()


def verify_quote(quote: str, source_norm: str):
    """Check a quote against already-normalised source text.

    Returns (ok, start, end, reason). reason is None when ok, otherwise one of
    "too_short", "too_long", "not_in_source".
    """
    q = normalize(quote or "")
    if len(q) < MIN_QUOTE_CHARS:
        return False, None, None, "too_short"
    if len(q) > MAX_QUOTE_CHARS:
        return False, None, None, "too_long"
    idx = source_norm.find(q)
    if idx == -1:
        return False, None, None, "not_in_source"
    return True, idx, idx + len(q), None
