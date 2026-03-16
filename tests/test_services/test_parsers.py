from anne.services.parsers import ParsedIdea, parse_kindle_export_html


KINDLE_BASIC = """
<html><body>
<div class="sectionHeading">Chapter 1</div>
<div class="noteHeading">Highlight (yellow) - Page 10 > Location 120</div>
<div class="noteText">This is a highlighted quote.</div>
</body></html>
"""

KINDLE_HIGHLIGHT_WITH_NOTE = """
<html><body>
<div class="noteHeading">Highlight (yellow) - Page 20 > Location 200</div>
<div class="noteText">A quote from the book.</div>
<div class="noteHeading">Note - Page 20 > Location 200</div>
<div class="noteText">My personal thought about this.</div>
</body></html>
"""

KINDLE_STANDALONE_NOTE = """
<html><body>
<div class="noteHeading">Note - Page 30 > Location 300</div>
<div class="noteText">A standalone thought, no preceding highlight.</div>
</body></html>
"""

KINDLE_EMPTY = "<html><body></body></html>"

KINDLE_MULTIPLE = """
<html><body>
<div class="sectionHeading">Part One</div>
<div class="noteHeading">Highlight (yellow) - Page 5 > Location 50</div>
<div class="noteText">First quote.</div>
<div class="noteHeading">Highlight (yellow) - Page 8 > Location 80</div>
<div class="noteText">Second quote.</div>
<div class="noteHeading">Note - Page 8 > Location 80</div>
<div class="noteText">Note on second quote.</div>
<div class="noteHeading">Note - Page 12 > Location 120</div>
<div class="noteText">Standalone note here.</div>
</body></html>
"""


def test_kindle_basic_highlight():
    ideas = parse_kindle_export_html(KINDLE_BASIC)
    assert len(ideas) == 1
    assert ideas[0].raw_quote == "This is a highlighted quote."
    assert ideas[0].raw_note is None
    assert ideas[0].raw_ref is not None
    assert "Chapter 1" in ideas[0].raw_ref
    assert "Page 10" in ideas[0].raw_ref


def test_kindle_highlight_with_note():
    ideas = parse_kindle_export_html(KINDLE_HIGHLIGHT_WITH_NOTE)
    assert len(ideas) == 1
    assert ideas[0].raw_quote == "A quote from the book."
    assert ideas[0].raw_note == "My personal thought about this."


def test_kindle_standalone_note():
    ideas = parse_kindle_export_html(KINDLE_STANDALONE_NOTE)
    assert len(ideas) == 1
    assert ideas[0].raw_quote is None
    assert ideas[0].raw_note == "A standalone thought, no preceding highlight."


def test_kindle_empty():
    ideas = parse_kindle_export_html(KINDLE_EMPTY)
    assert ideas == []


def test_kindle_multiple_entries():
    ideas = parse_kindle_export_html(KINDLE_MULTIPLE)
    assert len(ideas) == 3
    # First: highlight only
    assert ideas[0].raw_quote == "First quote."
    assert ideas[0].raw_note is None
    # Second: highlight + note
    assert ideas[1].raw_quote == "Second quote."
    assert ideas[1].raw_note == "Note on second quote."
    # Third: standalone note
    assert ideas[2].raw_quote is None
    assert ideas[2].raw_note == "Standalone note here."
