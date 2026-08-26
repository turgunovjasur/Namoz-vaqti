"""Supported Uzbekistan locations and exact IslomAPI identifiers."""

from dataclasses import dataclass

from namoz_bot.domain.errors import UnsupportedRegionError


@dataclass(frozen=True, slots=True)
class Region:
    """A user-facing label paired with the API's exact region value."""

    code: str
    display_name: str


DEFAULT_REGION_CODE = "Toshkent"


UZBEKISTAN_REGIONS: tuple[Region, ...] = (
    Region("\u041eltiariq", "Oltiariq"),
    Region("O'smat", "O‘smat"),
    Region("To'rtko'l", "To‘rtko‘l"),
    Region("Uzunquduq", "Uzunquduq"),
    Region("Jizzax", "Jizzax"),
    Region("\u041eltinko'l", "Oltinko‘l"),
    Region("Risht\u043en", "Rishton"),
    Region("Xo'ja\u043eb\u043ed", "Xo‘jaobod"),
    Region("Do'stlik", "Do‘stlik"),
    Region("Buxoro", "Buxoro"),
    Region("Termiz", "Termiz"),
    Region("Q\u043er\u043evulb\u043ez\u043er", "Qorovulbozor"),
    Region("X\u043enqa", "Xonqa"),
    Region("Tallimarj\u043en", "Tallimarjon"),
    Region("Uchqo'rg'\u043en", "Uchqo‘rg‘on"),
    Region("Uchtepa", "Uchtepa"),
    Region("X\u043en\u043eb\u043ed", "Xonobod"),
    Region(DEFAULT_REGION_CODE, "Toshkent"),
    Region("G'uz\u043er", "G‘uzor"),
    Region("Bek\u043eb\u043ed", "Bekobod"),
    Region("Navoiy", "Navoiy"),
    Region("Qo'rg'\u043entepa", "Qo‘rg‘ontepa"),
    Region("Mub\u043erak", "Muborak"),
    Region("\u041el\u043et", "Olot"),
    Region("Nur\u043eta", "Nurota"),
    Region("Andijon", "Andijon"),
    Region("Shumanay", "Shumanay"),
    Region("Namangan", "Namangan"),
    Region("Chimb\u043ey", "Chimboy"),
    Region("J\u043emb\u043ey", "Jomboy"),
    Region("Sher\u043eb\u043ed", "Sherobod"),
    Region("Mo'yn\u043eq", "Mo‘ynoq"),
    Region("Bul\u043eqb\u043eshi", "Buloqboshi"),
    Region("Uchquduq", "Uchquduq"),
    Region("Samarqand", "Samarqand"),
    Region("Qiziltepa", "Qiziltepa"),
    Region("Z\u043emin", "Zomin"),
    Region("T\u043emdi", "Tomdi"),
    Region("Yangib\u043ez\u043er", "Yangibozor"),
    Region("Nukus", "Nukus"),
    Region("Ch\u043ert\u043eq", "Chortoq"),
    Region("Taxtako'pir", "Taxtako‘pir"),
    Region("Xiva", "Xiva"),
    Region("K\u043es\u043ens\u043ey", "Kosonsoy"),
    Region("K\u043enimex", "Konimex"),
    Region("Mingbul\u043eq", "Mingbuloq"),
    Region("Paxta\u043eb\u043ed", "Paxtaobod"),
    Region("Den\u043ev", "Denov"),
    Region("O'g'iz", "O‘g‘iz"),
    Region("Qo'ng'ir\u043et", "Qo‘ng‘irot"),
    Region("Chust", "Chust"),
    Region("Kattaqo'rg'\u043en", "Kattaqo‘rg‘on"),
    Region("Farg'\u043ena", "Farg‘ona"),
    Region("Q\u043erako'l", "Qorako‘l"),
    Region("Arnas\u043ey", "Arnasoy"),
    Region("Angren", "Angren"),
    Region("P\u043ep", "Pop"),
    Region("G'alla\u043er\u043el", "G‘allaorol"),
    Region("Urgut", "Urgut"),
    Region("Shahrix\u043en", "Shahrixon"),
    Region("Guliston", "Guliston"),
    Region("Qumqo'rg'\u043en", "Qumqo‘rg‘on"),
    Region("B\u043eysun", "Boysun"),
    Region("Urganch", "Urganch"),
    Region("Qo'qon", "Qo‘qon"),
    Region("Gazli", "Gazli"),
    Region("Xaz\u043erasp", "Xazorasp"),
    Region("Marg'ilon", "Marg‘ilon"),
    Region("Sh\u043ev\u043et", "Shovot"),
    Region("Quva", "Quva"),
    Region("Burchmulla", "Burchmulla"),
    Region("Dehq\u043en\u043eb\u043ed", "Dehqonobod"),
    Region("Zarafsh\u043en", "Zarafshon"),
    Region("Qarshi", "Qarshi"),
    Region("K\u043es\u043en", "Koson"),
)

_REGIONS_BY_CODE = {region.code: region for region in UZBEKISTAN_REGIONS}


def list_regions() -> tuple[Region, ...]:
    """Return the immutable supported-region catalog."""

    return UZBEKISTAN_REGIONS


def get_region(code: str) -> Region:
    """Resolve an exact API region code or raise a typed error."""

    try:
        return _REGIONS_BY_CODE[code]
    except KeyError as exc:
        raise UnsupportedRegionError(f"Hudud qo‘llab-quvvatlanmaydi: {code}") from exc
