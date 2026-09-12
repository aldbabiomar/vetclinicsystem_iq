# -*- coding: utf-8 -*-
"""Arabic text must not be breakable between two letters.

Arabic is cursive. A line break inside a word severs the joined letterforms,
which is never a legal wrap point in the script — the three-letter backup
status نجح rendered as نج / ح on two lines.

The cause was `overflow-wrap: anywhere`, and the important part is that the
rule is **right for English**: a failure badge interpolates a raw error
message with no spaces to break at, and breaking it anywhere is what keeps it
inside the pill rather than stretching the table row. `anywhere` has a second
effect that produces the first — it drops the element's min-content width to a
single character, so a narrow column collapses around it and the word then
HAS to break to fit. Measured on the backup status badge: 32px tall (two
lines) with `anywhere`, 19px (one) with `break-word`.

So the fix is scoped to `html[dir="rtl"]` and English renders exactly as it
did. `break-word` still breaks a token that cannot fit a line on its own, so
Arabic keeps the overflow protection too; it just will not break a word that
could stay whole.

This file asserts the SHAPE of that fix, not that no rule may use `anywhere`.
"""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "static" / "style.css"


def _css():
    """Comments explain these rules and quote the property names they
    discuss, so a scanner reading raw text flags the comment that documents
    the fix. Strip them first."""
    return re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)


def _selectors_breaking_anywhere(src):
    out = []
    for m in re.finditer(r"([^{}]+)\{([^}]*)\}", src):
        body = m.group(2)
        if "overflow-wrap" in body and "anywhere" in body:
            for sel in m.group(1).replace("\n", " ").split(","):
                out.append(sel.strip())
    return [s for s in out if s]


def _selectors_with_rtl_override(src):
    out = []
    for m in re.finditer(r"([^{}]+)\{([^}]*)\}", src):
        body = m.group(2)
        if "overflow-wrap" in body and "break-word" in body:
            for sel in m.group(1).replace("\n", " ").split(","):
                sel = sel.strip()
                if sel.startswith('html[dir="rtl"]'):
                    out.append(sel[len('html[dir="rtl"]'):].strip())
    return out


def test_text_that_breaks_anywhere_has_an_arabic_override():
    """Every element that may break mid-word must be exempted in RTL —
    unless its content genuinely has no word boundaries."""
    src = _css()
    # content that is a path, a URL or an opaque token: there is nothing to
    # break AT, so breaking anywhere is the only way to keep it on screen,
    # and none of it is Arabic prose.
    NO_WORDS = {".list-line > *", ".vz-progress-label", ".vz-toast-msg",
                ".vz-confirm-msg", ".pos-cart-line > *:first-child"}
    breaking = set(_selectors_breaking_anywhere(src)) - NO_WORDS
    overridden = set(_selectors_with_rtl_override(src))
    missing = sorted(s for s in breaking if s not in overridden)
    assert not missing, (
        "These carry translated prose and may break between any two "
        f"characters, which severs cursive Arabic: {missing}. Add an "
        'html[dir="rtl"] … { overflow-wrap: break-word; } override — do not '
        "change the English rule, which is correct as it stands.")


def test_the_status_badge_is_overridden_in_arabic():
    """The one a clinic actually reported: نجح split across two lines."""
    assert ".badge" in _selectors_with_rtl_override(_css()), (
        "the status badge has no RTL wrapping override, so a short Arabic "
        "word can still be broken between its letters")


def test_english_still_breaks_anywhere():
    """CONTROL. The point of scoping this to RTL is that English is
    unchanged — a guard that passed by removing the English rule would be
    fixing the wrong thing."""
    assert ".badge" in _selectors_breaking_anywhere(_css()), (
        "the English .badge rule no longer breaks anywhere — a long error "
        "message will stretch the table row instead of wrapping in the pill")


def test_control_the_scanner_reads_the_stylesheet():
    src = _css()
    assert len(re.findall(r"[^{}]+\{[^}]*\}", src)) > 200, "stylesheet not parsed"
    assert _selectors_breaking_anywhere(src), "no overflow-wrap rules found at all"
