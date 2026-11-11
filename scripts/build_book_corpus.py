"""Prepare a replaceable local book corpus without calling any AI service.

Requires pdfplumber (available in the Codex bundled Python runtime).
Review the extracted passages against the original PDF before enabling.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pdfplumber

from namoz_bot.infrastructure.books import NUMBERED_ENTRY, BookCorpus, extract_passages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--translator", default="")
    parser.add_argument("--structure", choices=["auto", "numbered", "paragraphs"], default="auto")
    parser.add_argument("--entry-pattern", default=NUMBERED_ENTRY,
                        help="Regex with named reference and text groups for numbered entries")
    args = parser.parse_args()
    with pdfplumber.open(args.pdf) as document:
        pages = [page.extract_text() or "" for page in document.pages]
    passages = extract_passages(pages, structure=args.structure, entry_pattern=args.entry_pattern)
    if args.output.exists():
        previous = BookCorpus.load(args.output)
        # Keep existing bookmark IDs when a short-only corpus is expanded.
        by_reference = {p.reference: p.id for p in previous.passages if p.reference}
        by_text = {p.text: p.id for p in previous.passages if not p.reference}
        for passage in passages:
            identifier = (
                by_reference.get(passage.reference)
                if passage.reference else by_text.get(passage.text)
            )
            if identifier:
                passage.id = identifier
    book = BookCorpus(
        title=args.title,
        author=args.author,
        translator=args.translator,
        passages=passages,
    )
    data = book.model_dump()
    data["source_pdf"] = args.pdf.name
    data["source_sha256"] = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    data["extraction"] = {
        "structure": args.structure,
        "entry_pattern": args.entry_pattern,
        "page_count": len(pages),
        "pages_without_text": [i for i, page in enumerate(pages, 1) if not page.strip()],
        "max_chars": None,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(book.passages)} complete passages from {len(pages)} pages: {args.output}")
    if data["extraction"]["pages_without_text"]:
        print("Pages without extractable text (review blank pages / OCR scans):",
              data["extraction"]["pages_without_text"])


if __name__ == "__main__":
    main()
