import importlib
import json

import httpx
import pytest
from pydantic import SecretStr

from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.infrastructure.gemini import GeminiReminderClient


def test_numbered_book_extraction_preserves_cross_page_passage_and_stops_at_chapter():
    module = importlib.import_module("namoz_bot.infrastructure.books")
    passages = module.extract_passages(
        [
            "Kitob sarlavhasi\n1-BOB\nBob izohi\n1/1. Birinchi parcha davom etadi",
            "Kitob sarlavhasi\nva shu yerda tugaydi.\n2/2. Ikkinchi to‘liq parcha.\n"
            "2-BOB\nYangi bob izohi",
        ],
        min_chars=1,
        max_chars=900,
    )
    assert passages[0].text == "Birinchi parcha davom etadi va shu yerda tugaydi."
    assert passages[0].page_start == 1
    assert passages[0].page_end == 2
    assert passages[1].text == "Ikkinchi to‘liq parcha."
    assert passages[1].reference == "2/2"


def test_other_book_without_hadith_numbers_uses_complete_paragraphs():
    module = importlib.import_module("namoz_bot.infrastructure.books")
    passages = module.extract_passages(
        ["Birinchi nasihat.\n\nIkkinchi nasihat."], min_chars=1, max_chars=900
    )
    assert [p.text for p in passages] == ["Birinchi nasihat.", "Ikkinchi nasihat."]


def test_unnumbered_paragraph_continues_across_pages_without_cutting():
    module = importlib.import_module("namoz_bot.infrastructure.books")
    passages = module.extract_passages(
        [
            "Birinchi sahifada boshlangan",
            "nasihat ikkinchi sahifada tugaydi.\n\nKeyingi to‘liq nasihat.",
        ],
        min_chars=1,
    )
    assert len(passages) == 2
    assert passages[0].text == "Birinchi sahifada boshlangan nasihat ikkinchi sahifada tugaydi."
    assert (passages[0].page_start, passages[0].page_end) == (1, 2)


def test_long_cross_page_paragraph_is_skipped_whole_without_suffix():
    module = importlib.import_module("namoz_bot.infrastructure.books")
    passages = module.extract_passages(["a" * 901, "Tugashi.\n\nKeyingi nasihat."], min_chars=1)
    assert [p.text for p in passages] == ["Keyingi nasihat."]


def test_numbered_footer_never_enters_source_passages():
    module = importlib.import_module("namoz_bot.infrastructure.books")
    passages = module.extract_passages(
        [
            "1/1. Birinchi nasihat.\nKutubxona 1",
            "2/2. Ikkinchi nasihat.\nKutubxona 2",
        ],
        min_chars=1,
    )
    assert passages[0].text == "Birinchi nasihat."
    assert passages[1].text == "Ikkinchi nasihat."


def write_book(tmp_path, *, title="Boshqa kitob", passages=None):
    path = tmp_path / "book.json"
    path.write_text(
        json.dumps(
            {
                "title": title,
                "author": "Muallif",
                "translator": "Tarjimon",
                "passages": passages
                or [
                    {
                        "id": "p1",
                        "text": "Kitobdagi asl nasihat.",
                        "page_start": 12,
                        "page_end": 13,
                        "reference": "7/2",
                    },
                    {
                        "id": "p2",
                        "text": "Kitobdagi ikkinchi nasihat.",
                        "page_start": 20,
                        "page_end": 20,
                        "reference": "9/1",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def response(text):
    return httpx.Response(
        200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]}}]}
    )


async def test_gemini_only_selects_and_local_book_supplies_text_and_citation(tmp_path):
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return response('{"passage_id":"p1", "text":"Tashqi uydirma matn"}')

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = GeminiReminderClient(
            http,
            api_key=SecretStr("test-key"),
            model="test-model",
            corpus_path=write_book(tmp_path),
        )
        result = await client.generate()

    assert "Kitobdagi asl nasihat." in result
    assert "Boshqa kitob" in result
    assert "12–13" in result
    assert "7/2" in result
    assert "Tashqi uydirma matn" not in result
    prompt = requests[0]["contents"][0]["parts"][0]["text"]
    assert "Boshqa kitob" in prompt
    assert "Kitobdagi asl nasihat." in prompt
    assert "Riyozus" not in requests[0]["systemInstruction"]["parts"][0]["text"]


@pytest.mark.parametrize("answer", ["Yangi nasihat.", '{"passage_id":"invented"}', "{}"])
async def test_unverified_model_content_never_becomes_a_reminder(tmp_path, answer):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response(answer))) as http:
        client = GeminiReminderClient(
            http,
            api_key=SecretStr("test-key"),
            model="test-model",
            corpus_path=write_book(tmp_path),
        )
        with pytest.raises(ExternalServiceError):
            await client.generate()


async def test_next_request_excludes_last_selected_passage(tmp_path):
    seen = []

    def respond(request):
        body = json.loads(request.content)
        options = body["generationConfig"]["responseSchema"]["properties"]["passage_id"]["enum"]
        seen.append(options)
        return response(json.dumps({"passage_id": options[0]}))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = GeminiReminderClient(
            http,
            api_key=SecretStr("test-key"),
            model="test-model",
            corpus_path=write_book(tmp_path),
        )
        first = await client.generate()
        second = await client.generate()
    assert first != second
    assert seen[0][0] not in seen[1]


@pytest.mark.parametrize("data", [{}, {"title": "Kitob", "author": "Muallif", "passages": []}])
async def test_missing_or_invalid_book_fails_closed(tmp_path, data):
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    async with httpx.AsyncClient() as http:
        with pytest.raises(ValueError, match="kitob"):
            GeminiReminderClient(
                http, api_key=SecretStr("test-key"), model="test-model", corpus_path=path
            )


async def test_model_cannot_select_valid_book_passage_outside_offered_batch(tmp_path):
    passages = [
        {"id": f"p{i}", "text": f"Asl matn {i}.", "page_start": 1, "page_end": 1, "reference": ""}
        for i in range(20)
    ]

    def respond(request):
        body = json.loads(request.content)
        offered = body["generationConfig"]["responseSchema"]["properties"]["passage_id"]["enum"]
        outside = next(p["id"] for p in passages if p["id"] not in offered)
        return response(json.dumps({"passage_id": outside}))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = GeminiReminderClient(
            http,
            api_key=SecretStr("test-key"),
            model="test-model",
            corpus_path=write_book(tmp_path, passages=passages),
        )
        with pytest.raises(ExternalServiceError):
            await client.generate()
