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

from namoz_bot.infrastructure.books import BookCorpus, extract_passages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--translator", default="")
    args = parser.parse_args()
    with pdfplumber.open(args.pdf) as document:
        pages = [page.extract_text() or "" for page in document.pages]
    book = BookCorpus(
        title=args.title,
        author=args.author,
        translator=args.translator,
        passages=extract_passages(pages),
    )
    data = book.model_dump()
    data["source_pdf"] = args.pdf.name
    data["source_sha256"] = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(book.passages)} complete passages from {len(pages)} pages: {args.output}")


if __name__ == "__main__":
    main()
