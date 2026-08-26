"""Supported Uzbekistan locations with provider-independent stable codes."""

from dataclasses import dataclass

from namoz_bot.domain.errors import UnsupportedRegionError


@dataclass(frozen=True, slots=True)
class Region:
    """A stable saved code, user-facing label, and external provider slug."""

    code: str
    display_name: str
    provider_key: str


DEFAULT_REGION_CODE = "Toshkent"


UZBEKISTAN_REGIONS: tuple[Region, ...] = (
    Region("\u041eltiariq", "Oltiariq", "oltiariq"),
    Region("To'rtko'l", "To‘rtko‘l", "tortkol-shahri"),
    Region("Jizzax", "Jizzax", "jizzax-shahri"),
    Region("\u041eltinko'l", "Oltinko‘l", "oltinkol"),
    Region("Risht\u043en", "Rishton", "rishton"),
    Region("Xo'ja\u043eb\u043ed", "Xo‘jaobod", "xojaobod"),
    Region("Do'stlik", "Do‘stlik", "dostlik"),
    Region("Buxoro", "Buxoro", "buxoro-shahri"),
    Region("Termiz", "Termiz", "termiz-shahri"),
    Region("Q\u043er\u043evulb\u043ez\u043er", "Qorovulbozor", "qorovulbozor"),
    Region("X\u043enqa", "Xonqa", "xonqa"),
    Region("Uchqo'rg'\u043en", "Uchqo‘rg‘on", "uchqorgon"),
    Region("Uchtepa", "Uchtepa", "uchtepa"),
    Region("X\u043en\u043eb\u043ed", "Xonobod", "xonobod-shahri"),
    Region(DEFAULT_REGION_CODE, "Toshkent", "toshkent-shahri"),
    Region("G'uz\u043er", "G‘uzor", "guzor"),
    Region("Bek\u043eb\u043ed", "Bekobod", "bekobod-shahri"),
    Region("Navoiy", "Navoiy", "navoiy-shahri"),
    Region("Qo'rg'\u043entepa", "Qo‘rg‘ontepa", "qorgontepa"),
    Region("Mub\u043erak", "Muborak", "muborak"),
    Region("\u041el\u043et", "Olot", "olot"),
    Region("Nur\u043eta", "Nurota", "nurota"),
    Region("Andijon", "Andijon", "andijon-shahri"),
    Region("Shumanay", "Shumanay", "shumanay"),
    Region("Namangan", "Namangan", "namangan-shahri"),
    Region("Chimb\u043ey", "Chimboy", "chimboy-shahri"),
    Region("J\u043emb\u043ey", "Jomboy", "jomboy"),
    Region("Sher\u043eb\u043ed", "Sherobod", "sherobod"),
    Region("Mo'yn\u043eq", "Mo‘ynoq", "moynoq"),
    Region("Bul\u043eqb\u043eshi", "Buloqboshi", "buloqboshi"),
    Region("Uchquduq", "Uchquduq", "uchquduq"),
    Region("Samarqand", "Samarqand", "samarqand-shahri"),
    Region("Qiziltepa", "Qiziltepa", "qiziltepa"),
    Region("Z\u043emin", "Zomin", "zomin"),
    Region("T\u043emdi", "Tomdi", "tomdi"),
    Region("Yangib\u043ez\u043er", "Yangibozor", "yangibozor"),
    Region("Nukus", "Nukus", "nukus-shahri"),
    Region("Ch\u043ert\u043eq", "Chortoq", "chortoq"),
    Region("Taxtako'pir", "Taxtako‘pir", "taxtakopir"),
    Region("Xiva", "Xiva", "xiva-shahri"),
    Region("K\u043es\u043ens\u043ey", "Kosonsoy", "kosonsoy"),
    Region("K\u043enimex", "Konimex", "konimex"),
    Region("Mingbul\u043eq", "Mingbuloq", "mingbuloq"),
    Region("Paxta\u043eb\u043ed", "Paxtaobod", "paxtaobod"),
    Region("Den\u043ev", "Denov", "denov-shahri"),
    Region("Qo'ng'ir\u043et", "Qo‘ng‘irot", "kungirot-shahri"),
    Region("Chust", "Chust", "chust"),
    Region("Kattaqo'rg'\u043en", "Kattaqo‘rg‘on", "kattaqorgon-shahri"),
    Region("Farg'\u043ena", "Farg‘ona", "fargona-shahri"),
    Region("Q\u043erako'l", "Qorako‘l", "qorakol"),
    Region("Arnas\u043ey", "Arnasoy", "arnasoy"),
    Region("Angren", "Angren", "angren"),
    Region("P\u043ep", "Pop", "pop"),
    Region("G'alla\u043er\u043el", "G‘allaorol", "gallaorol"),
    Region("Urgut", "Urgut", "urgut"),
    Region("Shahrix\u043en", "Shahrixon", "shahrixon"),
    Region("Guliston", "Guliston", "guliston-shahri"),
    Region("Qumqo'rg'\u043en", "Qumqo‘rg‘on", "qumqorgon"),
    Region("B\u043eysun", "Boysun", "boysun"),
    Region("Urganch", "Urganch", "urganch-shahri"),
    Region("Qo'qon", "Qo‘qon", "qoqon-shahri"),
    Region("Xaz\u043erasp", "Xazorasp", "xazorasp"),
    Region("Marg'ilon", "Marg‘ilon", "marghilon-shahri"),
    Region("Sh\u043ev\u043et", "Shovot", "shovot"),
    Region("Quva", "Quva", "quva"),
    Region("Dehq\u043en\u043eb\u043ed", "Dehqonobod", "dehqonobod"),
    Region("Zarafsh\u043en", "Zarafshon", "zarafshon-shahri"),
    Region("Qarshi", "Qarshi", "qarshi-shahri"),
    Region("K\u043es\u043en", "Koson", "koson"),
    Region("Asaka", "Asaka", "asaka-shahri"),
    Region("Kogon", "Kogon", "kogon-shahri"),
    Region("Shahrisabz", "Shahrisabz", "shahrisabz-shahri"),
    Region("Chirchiq", "Chirchiq", "chirchiq"),
    Region("Olmaliq", "Olmaliq", "olmaliq"),
    Region("Nurafshon", "Nurafshon", "nurafshon"),
)

_REGIONS_BY_CODE = {region.code: region for region in UZBEKISTAN_REGIONS}


def list_regions() -> tuple[Region, ...]:
    """Return the immutable supported-region catalog."""

    return UZBEKISTAN_REGIONS


def get_region(code: str) -> Region:
    """Resolve a stable saved region code or raise a typed error."""

    try:
        return _REGIONS_BY_CODE[code]
    except KeyError as exc:
        raise UnsupportedRegionError(f"Hudud qo‘llab-quvvatlanmaydi: {code}") from exc
