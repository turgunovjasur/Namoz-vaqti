"""Local book metadata and complete, source-preserving passages."""

import hashlib
import re
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class BookPassage(BaseModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    reference: str = ""

    @model_validator(mode="after")
    def validate_pages(self) -> "BookPassage":
        if self.page_end < self.page_start:
            raise ValueError("Invalid page range")
        return self


class BookCorpus(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=200)
    translator: str = Field(default="", max_length=200)
    passages: list[BookPassage] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ids(self) -> "BookCorpus":
        if len({p.id for p in self.passages}) != len(self.passages):
            raise ValueError("Duplicate passage IDs")
        return self

    @classmethod
    def load(cls, path: Path) -> "BookCorpus":
        try:
            return cls.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"Nasihat uchun kitob fayli yaroqsiz: {path}") from exc

    def format_passage(self, passage: BookPassage) -> str:
        pages = str(passage.page_start)
        if passage.page_end != passage.page_start:
            pages += f"–{passage.page_end}"
        reference = f", {passage.reference}-raqamli parcha" if passage.reference else ""
        translator = f"\nTarjima: {self.translator}." if self.translator else ""
        return (
            f"{passage.text}\n\nManba: «{self.title}», {self.author}."
            f"{translator}\nPDF sahifasi: {pages}{reference}."
        )


NUMBERED_ENTRY = r"^(?P<reference>\d+/\d+)(?:\s*\.\s*|\s+)(?P<text>.*)"
CHAPTER_HEADING = r"^\d+\s*[-–]\s*BOB\b"


def clean_book_pages(pages: list[str]) -> list[list[str]]:
    """Remove repeated margin labels only, preserving matching body text."""
    lines_by_page = [page.splitlines() for page in pages]

    def edge_key(line: str) -> str:
        return re.sub(r"\s+\d+$", "", line.strip())

    edges: Counter[str] = Counter()
    for lines in lines_by_page:
        nonempty = [line.strip() for line in lines if line.strip()]
        if nonempty:
            edges.update({edge_key(nonempty[0]), edge_key(nonempty[-1])})
    repeated = {line for line, count in edges.items() if count > 1}
    cleaned = []
    for lines in lines_by_page:
        content = [line.strip() for line in lines]
        nonempty = [i for i, line in enumerate(content) if line]
        if nonempty:
            for i in {nonempty[0], nonempty[-1]}:
                line = content[i]
                # A numbered entry or chapter heading is never a running header.
                is_body = re.match(NUMBERED_ENTRY, line) or re.match(CHAPTER_HEADING, line, re.I)
                if not is_body and (edge_key(line) in repeated or re.fullmatch(r"\d+", line)):
                    content[i] = ""
        cleaned.append(content)
    return cleaned


def extract_passages(
    pages: list[str], *, structure: str = "auto", entry_pattern: str = NUMBERED_ENTRY
) -> list[BookPassage]:
    """Keep all body text, splitting only at structural boundaries.

    Numbered books: an entry continues through page breaks until the next entry
    or chapter. Chapter introductions stay with that chapter's first entry.
    Prefaces and trailing sections are retained. Paragraph mode uses explicit
    blank lines; a page break alone never ends a passage. There is no length cap.
    """
    if structure not in {"auto", "numbered", "paragraphs"}:
        raise ValueError("Unknown book structure")
    numbered = re.compile(entry_pattern)
    if not {"reference", "text"}.issubset(numbered.groupindex):
        raise ValueError("Entry pattern needs named reference and text groups")
    chapter = re.compile(CHAPTER_HEADING, re.IGNORECASE)
    cleaned = clean_book_pages(pages)
    if entry_pattern == NUMBERED_ENTRY and structure != "paragraphs":
        # Some PDFs place the next numbered entry after a sentence on the same line.
        cleaned = [
            [part for line in lines for part in re.split(
                r"(?<=\S)[ \t]+(?=\d+/\d+(?:\s*\.|\s+))", line
            )]
            for lines in cleaned
        ]
    has_numbers = structure == "numbered" or (
        structure == "auto" and any(numbered.match(line) for lines in cleaned for line in lines)
    )
    if structure == "numbered" and not any(
        numbered.match(line) for lines in cleaned for line in lines
    ):
        raise ValueError("No numbered entries found; check the book structure")
    result: list[BookPassage] = []
    current: list[str] = []
    reference = ""
    chapter_intro = False
    start = end = 1
    used_ids: Counter[str] = Counter()

    def finish() -> None:
        text = " ".join(" ".join(current).split())
        if text:
            base = "entry-" + reference.replace("/", "-") if reference else (
                "section-" + hashlib.sha256(text.encode()).hexdigest()[:16]
            )
            used_ids[base] += 1
            identifier = base if used_ids[base] == 1 else f"{base}-{used_ids[base]}"
            result.append(BookPassage(
                id=identifier, text=text, page_start=start, page_end=end, reference=reference
            ))
        current.clear()

    for page_number, lines in enumerate(cleaned, 1):
        # Margin whitespace at a page break does not split a continuing paragraph.
        nonempty = [i for i, line in enumerate(lines) if line]
        if not nonempty:
            continue
        for line in lines[nonempty[0]:nonempty[-1] + 1]:
            match = numbered.match(line) if has_numbers else None
            if match:
                if not chapter_intro:
                    finish()
                if not current:
                    start = page_number
                reference = match.group("reference")
                current.append(match.group("text"))
                end = page_number
                chapter_intro = False
            elif has_numbers and chapter.match(line):
                finish()
                reference = ""
                chapter_intro = True
                start = end = page_number
                current.append(line)
            elif not has_numbers and not line:
                finish()
            elif line:
                if not current:
                    start = page_number
                end = page_number
                current.append(line)
    finish()
    return result
