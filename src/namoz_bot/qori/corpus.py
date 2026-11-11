"""The unmodified Tanzil Uthmani text, indexed in mushaf order."""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

ASSETS = Path(__file__).with_name("assets")
NAMES = (
    "Fotiha|Baqara|Oli Imron|Niso|Moida|An’om|A’rof|Anfol|Tavba|Yunus|Hud|Yusuf|"
    "Ra’d|Ibrohim|Hijr|Nahl|Isro|Kahf|Maryam|Toha|Anbiyo|Haj|Mo‘minun|Nur|Furqon|"
    "Shuaro|Naml|Qasas|Ankabut|Rum|Luqmon|Sajda|Ahzob|Saba’|Fotir|Yosin|Soffot|"
    "Sod|Zumar|G‘ofir|Fussilat|Sho‘ro|Zuxruf|Duxon|Josiya|Ahqof|Muhammad|Fath|"
    "Hujurot|Qof|Zoriyot|Tur|Najm|Qamar|Rahmon|Voqea|Hadid|Mujodala|Hashr|Mumtahana|"
    "Sof|Juma|Munofiqun|Tag‘obun|Taloq|Tahrim|Mulk|Qalam|Hoqqa|Maorij|Nuh|Jin|"
    "Muzzammil|Muddassir|Qiyomat|Inson|Mursalot|Naba’|Noziot|Abasa|Takvir|Infitor|"
    "Mutaffifin|Inshiqoq|Buruj|Toriq|A’lo|G‘oshiya|Fajr|Balad|Shams|Layl|Zuho|Sharh|"
    "Tiyn|Alaq|Qadr|Bayyina|Zalzala|Odiyot|Qori’a|Takosur|Asr|Humaza|Fil|Quraysh|"
    "Mo’un|Kavsar|Kofirun|Nasr|Masad|Ixlos|Falaq|Nos"
).split("|")


@dataclass(frozen=True)
class Surah:
    number: int
    name: str
    verses: tuple[str, ...]


@cache
def chapters() -> tuple[Surah, ...]:
    groups: list[list[str]] = [[] for _ in NAMES]
    for line in (ASSETS / "quran-uthmani.txt").read_text("utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        chapter, verse, text = line.split("|", 2)
        group = groups[int(chapter) - 1]
        if int(verse) != len(group) + 1 or not text:
            raise ValueError(f"Invalid Tanzil record {chapter}:{verse}")
        group.append(text)
    if len(groups) != 114 or not all(groups) or sum(map(len, groups)) != 6236:
        raise ValueError("Incomplete Tanzil corpus")
    return tuple(Surah(i, name, tuple(groups[i - 1])) for i, name in enumerate(NAMES, 1))
