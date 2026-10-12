"""Local book metadata and complete, source-preserving passages."""

import re
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class BookPassage(BaseModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=900)
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


def extract_passages(
    pages: list[str], *, min_chars: int = 80, max_chars: int = 900
) -> list[BookPassage]:
    """Extract whole numbered entries, or whole paragraphs for other books.

    Repeated page headers/footers are removed. Long passages are skipped rather
    than cut mid-sentence. PDFs without paragraph separation need a reviewed
    JSON corpus instead of guessed paragraph boundaries.
    """
    lines_by_page = [page.splitlines() for page in pages]

    def edge_key(line: str) -> str:
        return re.sub(r"\s+\d+$", "", line.strip())

    edges: Counter[str] = Counter()
    for lines in lines_by_page:
        nonempty = [line.strip() for line in lines if line.strip()]
        if nonempty:
            edges.update({edge_key(line) for line in nonempty[:1] + nonempty[-1:]})
    repeated = {line for line, count in edges.items() if count > 1}
    cleaned = [
        [
            line.strip()
            for line in lines
            if edge_key(line) not in repeated and not re.fullmatch(r"\s*\d+\s*", line)
        ]
        for lines in lines_by_page
    ]
    numbered = re.compile(r"^(\d+/\d+)\.\s*(.*)")
    chapter = re.compile(r"^\d+\s*[-–]\s*BOB\b", re.IGNORECASE)
    has_numbers = any(numbered.match(line) for lines in cleaned for line in lines)
    result: list[BookPassage] = []
    current: list[str] = []
    reference = ""
    start = end = 1

    def finish() -> None:
        text = " ".join(" ".join(current).split())
        if min_chars <= len(text) <= max_chars:
            result.append(
                BookPassage(
                    id=f"p{len(result) + 1}",
                    text=text,
                    page_start=start,
                    page_end=end,
                    reference=reference,
                )
            )
        current.clear()

    for page_number, lines in enumerate(cleaned, 1):
        for line in lines:
            match = numbered.match(line) if has_numbers else None
            if match:
                finish()
                reference = match[1]
                start = end = page_number
                current.append(match[2])
            elif has_numbers and chapter.match(line):
                finish()
                reference = ""
            elif has_numbers:
                if reference and line:
                    current.append(line)
                    end = page_number
            elif not line:
                finish()
            else:
                if not current:
                    start = page_number
                end = page_number
                current.append(line)
    finish()
    return result
