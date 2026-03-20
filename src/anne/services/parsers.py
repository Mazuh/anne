import re
from dataclasses import dataclass
from html.parser import HTMLParser

from anne.models import Source, SourceType


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


# Content classes commonly used by SSR sites (Substack, blogs, etc.)
_CONTENT_CLASSES = ("body markup", "post-content", "article-content", "entry-content")

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_BLOCK_TAGS = {"p", "div", "li", "tr", "figcaption"}
_VOID_TAGS = {"br", "hr", "img", "input", "meta", "link", "source", "wbr", "area", "col", "embed", "track"}


def _has_content_class(cls: str) -> bool:
    """Check if a class string contains a known content container class."""
    classes = cls.split()
    for content_cls in _CONTENT_CLASSES:
        if all(part in classes for part in content_cls.split()):
            return True
    return False


class _ContentExtractor(HTMLParser):
    """Extract text from the main content area of an HTML page.

    Preserves lightweight structural markers so downstream LLMs
    can distinguish headings, blockquotes, and regular paragraphs.
    """

    def __init__(self) -> None:
        super().__init__()
        self._depth = 0
        self._capture = False
        self._text_parts: list[str] = []
        self._skip_tags = {"script", "style", "noscript", "svg"}
        self._skip_depth = 0
        self._in_blockquote = 0
        self._in_heading: str | None = None
        self._current_line: list[str] = []

    def _flush_line(self, prefix: str = "") -> None:
        text = " ".join(self._current_line).strip()
        self._current_line = []
        if text:
            self._text_parts.append(f"{prefix}{text}")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._skip_tags:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in _VOID_TAGS:
            return
        cls = dict(attrs).get("class", "") or ""
        if not self._capture:
            if _has_content_class(cls):
                self._capture = True
                self._depth = 1
                return
        if self._capture:
            self._depth += 1
            if tag == "blockquote":
                self._flush_line()
                self._in_blockquote += 1
            elif tag in _HEADING_TAGS:
                self._flush_line()
                self._in_heading = tag
            elif tag in _BLOCK_TAGS:
                self._flush_line()

    def handle_endtag(self, tag: str) -> None:
        if tag in self._skip_tags and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if self._skip_depth or tag in _VOID_TAGS:
            return
        if self._capture:
            if tag == "blockquote":
                prefix = "> " if self._in_blockquote else ""
                self._flush_line(prefix)
                self._in_blockquote = max(0, self._in_blockquote - 1)
            elif tag in _HEADING_TAGS and self._in_heading == tag:
                self._flush_line("## ")
                self._in_heading = None
            elif tag in _BLOCK_TAGS:
                prefix = "> " if self._in_blockquote else ""
                self._flush_line(prefix)
            self._depth -= 1
            if self._depth <= 0:
                self._flush_line()
                self._capture = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._capture:
            stripped = data.strip()
            if stripped:
                self._current_line.append(stripped)

    def get_text(self) -> str:
        self._flush_line()
        return "\n".join(self._text_parts)


LLM_TYPES = {SourceType.essay_md, SourceType.essay_txt, SourceType.essay_html, SourceType.manual_notes}


def parse_source(source: Source, content: str, api_key: str | None, max_input_tokens: int) -> list[ParsedIdea] | None:
    """Parse a source file into ideas, dispatching by source type.

    Returns None for unknown/unsupported source types, or a (possibly empty)
    list for known types.
    """
    from anne.services.llm import parse_essay_with_llm

    source_type = SourceType(source.type)
    if source_type == SourceType.kindle_export_html:
        return parse_kindle_export_html(content)
    elif source_type in LLM_TYPES:
        if not api_key:
            raise ValueError("gemini_api_key is required for LLM-assisted parsing")
        if source_type == SourceType.essay_html:
            content = extract_html_content(content)
        return parse_essay_with_llm(api_key, content, max_input_tokens=max_input_tokens)
    else:
        return None


def extract_html_content(content: str) -> str:
    """Extract readable text from an HTML page.

    Tries to find a known content container (Substack, blogs, etc.).
    Falls back to stripping all tags if no content container is found.
    """
    extractor = _ContentExtractor()
    extractor.feed(content)
    text = extractor.get_text()
    if text:
        return text
    # Fallback: strip all tags (head/script/style first, then remaining tags)
    content = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", "", content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r"<[^>]+>", " ", content)
    return re.sub(r"\s+", " ", content).strip()
