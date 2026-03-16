from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass
class ParsedIdea:
    raw_quote: str | None = None
    raw_note: str | None = None
    raw_ref: str | None = None


class _KindleHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ideas: list[ParsedIdea] = []
        self._in_heading = False
        self._in_text = False
        self._in_section = False
        self._current_heading = ""
        self._current_text = ""
        self._current_section = ""
        self._heading_type: str | None = None  # "highlight" or "note"
        self._heading_ref: str | None = None
        self._last_was_highlight = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = dict(attrs).get("class", "") or ""
        if "noteHeading" in classes:
            self._in_heading = True
            self._current_heading = ""
        elif "noteText" in classes:
            self._in_text = True
            self._current_text = ""
        elif "sectionHeading" in classes:
            self._in_section = True
            self._current_section = ""

    def handle_endtag(self, tag: str) -> None:
        if self._in_section:
            self._in_section = False
            self._current_section = self._current_section.strip()
        elif self._in_heading:
            self._in_heading = False
            heading = self._current_heading.strip()
            self._parse_heading(heading)
        elif self._in_text:
            self._in_text = False
            text = self._current_text.strip()
            if not text:
                return
            self._apply_text(text)

    def handle_data(self, data: str) -> None:
        if self._in_heading:
            self._current_heading += data
        elif self._in_text:
            self._current_text += data
        elif self._in_section:
            self._current_section += data

    def _parse_heading(self, heading: str) -> None:
        heading_lower = heading.lower()
        if "highlight" in heading_lower or "destaque" in heading_lower:
            self._heading_type = "highlight"
        elif "note" in heading_lower or "nota" in heading_lower:
            self._heading_type = "note"
        else:
            self._heading_type = None
            return

        # Extract location/page reference from heading
        ref_parts: list[str] = []
        if self._current_section:
            ref_parts.append(self._current_section)
        # Extract everything after the type indicator (page/location info)
        # Heading format: "Highlight (yellow) - Page 42 > Location 123"
        # or Portuguese: "Destaque (amarelo) - Página 42 > Posição 123"
        for sep in [" - ", " > "]:
            if sep in heading:
                ref_part = heading.split(sep, 1)[1].strip()
                ref_parts.append(ref_part)
                break
        self._heading_ref = " | ".join(ref_parts) if ref_parts else None

    def _apply_text(self, text: str) -> None:
        if self._heading_type == "highlight":
            idea = ParsedIdea(raw_quote=text, raw_ref=self._heading_ref)
            self.ideas.append(idea)
            self._last_was_highlight = True
        elif self._heading_type == "note":
            if self._last_was_highlight and self.ideas:
                # Attach note to preceding highlight
                self.ideas[-1].raw_note = text
            else:
                # Standalone note
                idea = ParsedIdea(raw_note=text, raw_ref=self._heading_ref)
                self.ideas.append(idea)
            self._last_was_highlight = False
        else:
            self._last_was_highlight = False


def parse_kindle_export_html(content: str) -> list[ParsedIdea]:
    parser = _KindleHTMLParser()
    parser.feed(content)
    return parser.ideas
