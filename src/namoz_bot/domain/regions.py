"""Supported Uzbekistan locations grouped for Telegram selection."""

# ruff: noqa: RUF001  # Stable legacy DB codes intentionally contain Cyrillic lookalikes.

from dataclasses import dataclass

from namoz_bot.domain.errors import UnsupportedRegionError


@dataclass(frozen=True, slots=True)
class Region:
    """A stable saved code, label, canonical provider slug, and UI group."""

    code: str
    display_name: str
    provider_key: str
    group_code: str


@dataclass(frozen=True, slots=True)
class RegionGroup:
    """A top-level geographic group shown before its locations."""

    code: str
    display_name: str


DEFAULT_REGION_CODE = "Toshkent"


UZBEKISTAN_REGION_GROUPS: tuple[RegionGroup, ...] = (
    RegionGroup("toshkent-shahri", "Toshkent shahri"),
    RegionGroup("toshkent-viloyati", "Toshkent viloyati"),
    RegionGroup("sirdaryo-viloyati", "Sirdaryo viloyati"),
    RegionGroup("jizzax-viloyati", "Jizzax viloyati"),
    RegionGroup("samarqand-viloyati", "Samarqand viloyati"),
    RegionGroup("namangan-viloyati", "Namangan viloyati"),
    RegionGroup("fargona-viloyati", "Farg‘ona viloyati"),
    RegionGroup("andijon-viloyati", "Andijon viloyati"),
    RegionGroup("buxoro-viloyati", "Buxoro viloyati"),
    RegionGroup("navoiy-viloyati", "Navoiy viloyati"),
    RegionGroup("qashqadaryo-viloyati", "Qashqadaryo viloyati"),
    RegionGroup("surxondaryo-viloyati", "Surxondaryo viloyati"),
    RegionGroup("xorazm-viloyati", "Xorazm viloyati"),
    RegionGroup("qoraqalpogiston", "Qoraqalpog‘iston Respublikasi"),
)


UZBEKISTAN_REGIONS: tuple[Region, ...] = (
    Region("Toshkent", "Toshkent shahri", "toshkent-shahri", "toshkent-shahri"),
    Region("bektemir", "Bektemir", "bektemir", "toshkent-shahri"),
    Region("chilonzor", "Chilonzor", "chilonzor", "toshkent-shahri"),
    Region("mirobod", "Mirobod", "mirobod", "toshkent-shahri"),
    Region("mirzo-ulugbek", "Mirzo Ulug‘bek", "mirzo-ulugbek", "toshkent-shahri"),
    Region("sergeli", "Sergeli", "sergeli", "toshkent-shahri"),
    Region("shayxontohur", "Shayxontohur", "shayxontohur", "toshkent-shahri"),
    Region("Uchtepa", "Uchtepa", "uchtepa", "toshkent-shahri"),
    Region("olmazor", "Olmazor", "olmazor", "toshkent-shahri"),
    Region("yakkasaroy", "Yakkasaroy", "yakkasaroy", "toshkent-shahri"),
    Region("yangihayot", "Yangihayot", "yangihayot", "toshkent-shahri"),
    Region("yashnobod", "Yashnobod", "yashnobod", "toshkent-shahri"),
    Region("yunusobod", "Yunusobod", "yunusobod", "toshkent-shahri"),
    Region("toshkent-viloyati", "Toshkent viloyati", "toshkent-viloyati", "toshkent-viloyati"),
    Region("Nurafshon", "Nurafshon", "nurafshon", "toshkent-viloyati"),
    Region("Angren", "Angren", "angren", "toshkent-viloyati"),
    Region("Bekоbоd", "Bekobod shahri", "bekobod-shahri", "toshkent-viloyati"),
    Region("Chirchiq", "Chirchiq", "chirchiq", "toshkent-viloyati"),
    Region("ohangaron-shahri", "Ohangaron shahri", "ohangaron-shahri", "toshkent-viloyati"),
    Region("Olmaliq", "Olmaliq", "olmaliq", "toshkent-viloyati"),
    Region("yangiyol-shahri", "Yangiyo‘l shahri", "yangiyol-shahri", "toshkent-viloyati"),
    Region("bekobod", "Bekobod tumani", "bekobod-shahri", "toshkent-viloyati"),
    Region("boka", "Bo‘ka tumani", "boka", "toshkent-viloyati"),
    Region("bostonliq", "Bo‘stonliq tumani", "bostonliq", "toshkent-viloyati"),
    Region("chinoz", "Chinoz tumani", "chinoz", "toshkent-viloyati"),
    Region("ohangaron", "Ohangaron tumani", "ohangaron-shahri", "toshkent-viloyati"),
    Region("oqqorgon", "Oqqo‘rg‘on tumani", "oqqorgon", "toshkent-viloyati"),
    Region("parkent", "Parkent tumani", "parkent", "toshkent-viloyati"),
    Region("piskent", "Piskent tumani", "piskent", "toshkent-viloyati"),
    Region("qibray", "Qibray tumani", "qibray", "toshkent-viloyati"),
    Region("quyichirchiq", "Quyi Chirchiq tumani", "quyichirchiq", "toshkent-viloyati"),
    Region("ortachirchiq", "O‘rta Chirchiq tumani", "ortachirchiq", "toshkent-viloyati"),
    Region("yangiyol", "Yangiyo‘l tumani", "yangiyol-shahri", "toshkent-viloyati"),
    Region("yuqorichirchiq", "Yuqori Chirchiq tumani", "yuqorichirchiq", "toshkent-viloyati"),
    Region("zangiota", "Zangiota tumani", "zangiota", "toshkent-viloyati"),
    Region("toshkent-tumani", "Toshkent tumani", "toshkent-tumani", "toshkent-viloyati"),
    Region("sirdaryo-viloyati", "Sirdaryo viloyati", "sirdaryo-viloyati", "sirdaryo-viloyati"),
    Region("Guliston", "Guliston shahri", "guliston-shahri", "sirdaryo-viloyati"),
    Region("shirin-shahri", "Shirin shahri", "shirin-shahri", "sirdaryo-viloyati"),
    Region("yangiyer-shahri", "Yangiyer shahri", "yangiyer-shahri", "sirdaryo-viloyati"),
    Region("boyovut", "Boyovut tumani", "boyovut", "sirdaryo-viloyati"),
    Region("guliston", "Guliston tumani", "guliston-shahri", "sirdaryo-viloyati"),
    Region("mirzaobod", "Mirzaobod tumani", "mirzaobod", "sirdaryo-viloyati"),
    Region("oqoltin", "Oqoltin tumani", "oqoltin", "sirdaryo-viloyati"),
    Region("sardoba", "Sardoba tumani", "sardoba", "sirdaryo-viloyati"),
    Region("sayxunobod", "Sayxunobod tumani", "sayxunobod", "sirdaryo-viloyati"),
    Region("sirdaryo", "Sirdaryo tumani", "sirdaryo", "sirdaryo-viloyati"),
    Region("xovos", "Xovos tumani", "xovos", "sirdaryo-viloyati"),
    Region("jizzax-viloyati", "Jizzax viloyati", "jizzax-viloyati", "jizzax-viloyati"),
    Region("Jizzax", "Jizzax shahri", "jizzax-shahri", "jizzax-viloyati"),
    Region("Arnasоy", "Arnasoy tumani", "arnasoy", "jizzax-viloyati"),
    Region("baxmal", "Baxmal tumani", "baxmal", "jizzax-viloyati"),
    Region("Do'stlik", "Do‘stlik tumani", "dostlik", "jizzax-viloyati"),
    Region("forish", "Forish tumani", "forish", "jizzax-viloyati"),
    Region("G'allaоrоl", "G‘allaorol tumani", "gallaorol", "jizzax-viloyati"),
    Region("jizzax", "Jizzax tumani", "jizzax-shahri", "jizzax-viloyati"),
    Region("mirzachol", "Mirzacho‘l tumani", "mirzachol", "jizzax-viloyati"),
    Region("paxtakor", "Paxtakor tumani", "paxtakor", "jizzax-viloyati"),
    Region("zafarobod", "Zafarobod tumani", "zafarobod", "jizzax-viloyati"),
    Region("zarbdor", "Zarbdor tumani", "zarbdor", "jizzax-viloyati"),
    Region("Zоmin", "Zomin tumani", "zomin", "jizzax-viloyati"),
    Region("samarqand-viloyati", "Samarqand viloyati", "samarqand-viloyati", "samarqand-viloyati"),
    Region("Samarqand", "Samarqand shahri", "samarqand-shahri", "samarqand-viloyati"),
    Region("Kattaqo'rg'оn", "Kattaqo‘rg‘on shahri", "kattaqorgon-shahri", "samarqand-viloyati"),
    Region("bulungur", "Bulung‘ur tumani", "bulungur", "samarqand-viloyati"),
    Region("ishtixon", "Ishtixon tumani", "ishtixon", "samarqand-viloyati"),
    Region("Jоmbоy", "Jomboy tumani", "jomboy", "samarqand-viloyati"),
    Region("kattaqorgon", "Kattaqo‘rg‘on tumani", "kattaqorgon", "samarqand-viloyati"),
    Region("narpay", "Narpay tumani", "narpay", "samarqand-viloyati"),
    Region("nurobod", "Nurobod tumani", "nurobod", "samarqand-viloyati"),
    Region("oqdaryo", "Oqdaryo tumani", "oqdaryo", "samarqand-viloyati"),
    Region("paxtachi", "Paxtachi tumani", "paxtachi", "samarqand-viloyati"),
    Region("payariq", "Payariq tumani", "payariq", "samarqand-viloyati"),
    Region("pastdargom", "Pastdarg‘om tumani", "pastdargom", "samarqand-viloyati"),
    Region("qoshrabot", "Qo‘shrabot tumani", "qoshrabot", "samarqand-viloyati"),
    Region("samarqand", "Samarqand tumani", "samarqand-shahri", "samarqand-viloyati"),
    Region("tayloq", "Tayloq tumani", "tayloq", "samarqand-viloyati"),
    Region("Urgut", "Urgut tumani", "urgut", "samarqand-viloyati"),
    Region("namangan-viloyati", "Namangan viloyati", "namangan-viloyati", "namangan-viloyati"),
    Region("Namangan", "Namangan shahri", "namangan-shahri", "namangan-viloyati"),
    Region("Chоrtоq", "Chortoq tumani", "chortoq", "namangan-viloyati"),
    Region("Chust", "Chust tumani", "chust", "namangan-viloyati"),
    Region("Kоsоnsоy", "Kosonsoy tumani", "kosonsoy", "namangan-viloyati"),
    Region("Mingbulоq", "Mingbuloq tumani", "mingbuloq", "namangan-viloyati"),
    Region("namangan", "Namangan tumani", "namangan-shahri", "namangan-viloyati"),
    Region("norin", "Norin tumani", "norin", "namangan-viloyati"),
    Region("Pоp", "Pop tumani", "pop", "namangan-viloyati"),
    Region("toraqorgon", "To‘raqo‘rg‘on tumani", "toraqorgon", "namangan-viloyati"),
    Region("Uchqo'rg'оn", "Uchqo‘rg‘on tumani", "uchqorgon", "namangan-viloyati"),
    Region("uychi", "Uychi tumani", "uychi", "namangan-viloyati"),
    Region("yangiqorgon", "Yangiqo‘rg‘on tumani", "yangiqorgon", "namangan-viloyati"),
    Region("fargona-viloyati", "Farg‘ona viloyati", "fargona-viloyati", "fargona-viloyati"),
    Region("Farg'оna", "Farg‘ona shahri", "fargona-shahri", "fargona-viloyati"),
    Region("Qo'qon", "Qo‘qon shahri", "qoqon-shahri", "fargona-viloyati"),
    Region("Marg'ilon", "Marg‘ilon shahri", "marghilon-shahri", "fargona-viloyati"),
    Region("quvasoy-shahri", "Quvasoy shahri", "quvasoy-shahri", "fargona-viloyati"),
    Region("beshariq", "Beshariq tumani", "beshariq", "fargona-viloyati"),
    Region("bogdod", "Bog‘dod tumani", "bogdod", "fargona-viloyati"),
    Region("buvayda", "Buvayda tumani", "buvayda", "fargona-viloyati"),
    Region("dangara", "Dang‘ara tumani", "dangara", "fargona-viloyati"),
    Region("fargona", "Farg‘ona tumani", "fargona-shahri", "fargona-viloyati"),
    Region("furqat", "Furqat tumani", "furqat", "fargona-viloyati"),
    Region("ozbekiston", "O‘zbekiston tumani", "ozbekiston", "fargona-viloyati"),
    Region("Оltiariq", "Oltiariq tumani", "oltiariq", "fargona-viloyati"),
    Region("qoshtepa", "Qo‘shtepa tumani", "qoshtepa", "fargona-viloyati"),
    Region("Quva", "Quva tumani", "quva", "fargona-viloyati"),
    Region("Rishtоn", "Rishton tumani", "rishton", "fargona-viloyati"),
    Region("sox", "So‘x tumani", "sox", "fargona-viloyati"),
    Region("toshloq", "Toshloq tumani", "toshloq", "fargona-viloyati"),
    Region("uchkoprik", "Uchko‘prik tumani", "uchkoprik", "fargona-viloyati"),
    Region("yozyovon", "Yozyovon tumani", "yozyovon", "fargona-viloyati"),
    Region("andijon-viloyati", "Andijon viloyati", "andijon-viloyati", "andijon-viloyati"),
    Region("Andijon", "Andijon shahri", "andijon-shahri", "andijon-viloyati"),
    Region("Xоnоbоd", "Xonobod shahri", "xonobod-shahri", "andijon-viloyati"),
    Region("Asaka", "Asaka shahri", "asaka-shahri", "andijon-viloyati"),
    Region("andijon", "Andijon tumani", "andijon-shahri", "andijon-viloyati"),
    Region("asaka", "Asaka tumani", "asaka", "andijon-viloyati"),
    Region("baliqchi", "Baliqchi tumani", "baliqchi", "andijon-viloyati"),
    Region("boston", "Bo‘ston tumani", "boston", "andijon-viloyati"),
    Region("Bulоqbоshi", "Buloqboshi tumani", "buloqboshi", "andijon-viloyati"),
    Region("izboskan", "Izboskan tumani", "izboskan", "andijon-viloyati"),
    Region("jalaquduq", "Jalaquduq tumani", "jalaquduq", "andijon-viloyati"),
    Region("marhamat", "Marhamat tumani", "marhamat", "andijon-viloyati"),
    Region("Оltinko'l", "Oltinko‘l tumani", "oltinkol", "andijon-viloyati"),
    Region("Paxtaоbоd", "Paxtaobod tumani", "paxtaobod", "andijon-viloyati"),
    Region("Qo'rg'оntepa", "Qo‘rg‘ontepa tumani", "qorgontepa", "andijon-viloyati"),
    Region("Shahrixоn", "Shahrixon tumani", "shahrixon", "andijon-viloyati"),
    Region("Xo'jaоbоd", "Xo‘jaobod tumani", "xojaobod", "andijon-viloyati"),
    Region("buxoro-viloyati", "Buxoro viloyati", "buxoro-viloyati", "buxoro-viloyati"),
    Region("Buxoro", "Buxoro shahri", "buxoro-shahri", "buxoro-viloyati"),
    Region("Kogon", "Kogon shahri", "kogon-shahri", "buxoro-viloyati"),
    Region("buxoro", "Buxoro tumani", "buxoro-shahri", "buxoro-viloyati"),
    Region("vobkent", "Vobkent tumani", "vobkent", "buxoro-viloyati"),
    Region("gijduvon", "G‘ijduvon tumani", "gijduvon", "buxoro-viloyati"),
    Region("jondor", "Jondor tumani", "jondor", "buxoro-viloyati"),
    Region("kogon", "Kogon tumani", "kogon", "buxoro-viloyati"),
    Region("Оlоt", "Olot tumani", "olot", "buxoro-viloyati"),
    Region("peshku", "Peshku tumani", "peshku", "buxoro-viloyati"),
    Region("Qоrako'l", "Qorako‘l tumani", "qorakol", "buxoro-viloyati"),
    Region("Qоrоvulbоzоr", "Qorovulbozor tumani", "qorovulbozor", "buxoro-viloyati"),
    Region("romitan", "Romitan tumani", "romitan", "buxoro-viloyati"),
    Region("shofirkon", "Shofirkon tumani", "shofirkon", "buxoro-viloyati"),
    Region("navoiy-viloyati", "Navoiy viloyati", "navoiy-viloyati", "navoiy-viloyati"),
    Region("Navoiy", "Navoiy shahri", "navoiy-shahri", "navoiy-viloyati"),
    Region("Zarafshоn", "Zarafshon shahri", "zarafshon-shahri", "navoiy-viloyati"),
    Region("karmana", "Karmana tumani", "karmana", "navoiy-viloyati"),
    Region("Qiziltepa", "Qiziltepa tumani", "qiziltepa", "navoiy-viloyati"),
    Region("xatirchi", "Xatirchi tumani", "xatirchi", "navoiy-viloyati"),
    Region("navbahor", "Navbahor tumani", "navbahor", "navoiy-viloyati"),
    Region("Nurоta", "Nurota tumani", "nurota", "navoiy-viloyati"),
    Region("Kоnimex", "Konimex tumani", "konimex", "navoiy-viloyati"),
    Region("Tоmdi", "Tomdi tumani", "tomdi", "navoiy-viloyati"),
    Region("Uchquduq", "Uchquduq tumani", "uchquduq", "navoiy-viloyati"),
    Region(
        "qashqadaryo-viloyati",
        "Qashqadaryo viloyati",
        "qashqadaryo-viloyati",
        "qashqadaryo-viloyati",
    ),
    Region("Qarshi", "Qarshi shahri", "qarshi-shahri", "qashqadaryo-viloyati"),
    Region("Shahrisabz", "Shahrisabz shahri", "shahrisabz-shahri", "qashqadaryo-viloyati"),
    Region("chiroqchi", "Chiroqchi tumani", "chiroqchi", "qashqadaryo-viloyati"),
    Region("Dehqоnоbоd", "Dehqonobod tumani", "dehqonobod", "qashqadaryo-viloyati"),
    Region("G'uzоr", "G‘uzor tumani", "guzor", "qashqadaryo-viloyati"),
    Region("kasbi", "Kasbi tumani", "kasbi", "qashqadaryo-viloyati"),
    Region("kitob", "Kitob tumani", "kitob", "qashqadaryo-viloyati"),
    Region("Kоsоn", "Koson tumani", "koson", "qashqadaryo-viloyati"),
    Region("mirishkor", "Mirishkor tumani", "mirishkor", "qashqadaryo-viloyati"),
    Region("Mubоrak", "Muborak tumani", "muborak", "qashqadaryo-viloyati"),
    Region("nishon", "Nishon tumani", "nishon", "qashqadaryo-viloyati"),
    Region("qarshi", "Qarshi tumani", "qarshi-shahri", "qashqadaryo-viloyati"),
    Region("qamashi", "Qamashi tumani", "qamashi", "qashqadaryo-viloyati"),
    Region("shahrisabz", "Shahrisabz tumani", "shahrisabz", "qashqadaryo-viloyati"),
    Region("yakkabog", "Yakkabog‘ tumani", "yakkabog", "qashqadaryo-viloyati"),
    Region(
        "surxondaryo-viloyati",
        "Surxondaryo viloyati",
        "surxondaryo-viloyati",
        "surxondaryo-viloyati",
    ),
    Region("Termiz", "Termiz shahri", "termiz-shahri", "surxondaryo-viloyati"),
    Region("Denоv", "Denov shahri", "denov-shahri", "surxondaryo-viloyati"),
    Region("angor", "Angor tumani", "angor", "surxondaryo-viloyati"),
    Region("bandixon", "Bandixon tumani", "bandixon", "surxondaryo-viloyati"),
    Region("Bоysun", "Boysun tumani", "boysun", "surxondaryo-viloyati"),
    Region("denov", "Denov tumani", "denov", "surxondaryo-viloyati"),
    Region("jarqorgon", "Jarqo‘rg‘on tumani", "jarqorgon", "surxondaryo-viloyati"),
    Region("muzrabot", "Muzrabot tumani", "muzrabot", "surxondaryo-viloyati"),
    Region("oltinsoy", "Oltinsoy tumani", "oltinsoy", "surxondaryo-viloyati"),
    Region("qiziriq", "Qiziriq tumani", "qiziriq", "surxondaryo-viloyati"),
    Region("Qumqo'rg'оn", "Qumqo‘rg‘on tumani", "qumqorgon", "surxondaryo-viloyati"),
    Region("sariosiyo", "Sariosiyo tumani", "sariosiyo", "surxondaryo-viloyati"),
    Region("Sherоbоd", "Sherobod tumani", "sherobod", "surxondaryo-viloyati"),
    Region("shorchi", "Sho‘rchi tumani", "shorchi", "surxondaryo-viloyati"),
    Region("termiz", "Termiz tumani", "termiz-shahri", "surxondaryo-viloyati"),
    Region("uzun", "Uzun tumani", "uzun", "surxondaryo-viloyati"),
    Region("xorazm-viloyati", "Xorazm viloyati", "xorazm-viloyati", "xorazm-viloyati"),
    Region("Urganch", "Urganch shahri", "urganch-shahri", "xorazm-viloyati"),
    Region("Xiva", "Xiva shahri", "xiva-shahri", "xorazm-viloyati"),
    Region("bogot", "Bog‘ot tumani", "bogot", "xorazm-viloyati"),
    Region("gurlan", "Gurlan tumani", "gurlan", "xorazm-viloyati"),
    Region("qoshkopir", "Qo‘shko‘pir tumani", "qoshkopir", "xorazm-viloyati"),
    Region("Shоvоt", "Shovot tumani", "shovot", "xorazm-viloyati"),
    Region("urganch", "Urganch tumani", "urganch-shahri", "xorazm-viloyati"),
    Region("Xazоrasp", "Xazorasp tumani", "xazorasp", "xorazm-viloyati"),
    Region("xiva", "Xiva tumani", "xiva-shahri", "xorazm-viloyati"),
    Region("Yangibоzоr", "Yangibozor tumani", "yangibozor", "xorazm-viloyati"),
    Region("yangiariq", "Yangiariq tumani", "yangiariq", "xorazm-viloyati"),
    Region("Xоnqa", "Xonqa tumani", "xonqa", "xorazm-viloyati"),
    Region("tuproqqala", "Tuproqqal’a tumani", "tuproqqala", "xorazm-viloyati"),
    Region(
        "qoraqalpogiston",
        "Qoraqalpog‘iston Respublikasi",
        "qoraqalpogiston",
        "qoraqalpogiston",
    ),
    Region("Nukus", "Nukus shahri", "nukus-shahri", "qoraqalpogiston"),
    Region("taxiatosh", "Taxiatosh shahri", "taxiatosh", "qoraqalpogiston"),
    Region("To'rtko'l", "To‘rtko‘l shahri", "tortkol-shahri", "qoraqalpogiston"),
    Region("amudaryo", "Amudaryo tumani", "amudaryo", "qoraqalpogiston"),
    Region("beruniy", "Beruniy tumani", "beruniy", "qoraqalpogiston"),
    Region("bozatov", "Bo‘zatov tumani", "bozatov", "qoraqalpogiston"),
    Region("chimboy", "Chimboy tumani", "chimboy", "qoraqalpogiston"),
    Region("ellikqala", "Ellikqal’a tumani", "ellikqala", "qoraqalpogiston"),
    Region("kegeyli", "Kegeyli tumani", "kegeyli", "qoraqalpogiston"),
    Region("Mo'ynоq", "Mo‘ynoq tumani", "moynoq", "qoraqalpogiston"),
    Region("nukus-tumani", "Nukus tumani", "nukus-tumani", "qoraqalpogiston"),
    Region("qanlikol", "Qanliko‘l tumani", "qanlikol", "qoraqalpogiston"),
    Region("qoraozak", "Qorao‘zak tumani", "qoraozak", "qoraqalpogiston"),
    Region("kungirot", "Qo‘ng‘irot tumani", "kungirot", "qoraqalpogiston"),
    Region("Shumanay", "Shumanay tumani", "shumanay", "qoraqalpogiston"),
    Region("Taxtako'pir", "Taxtako‘pir tumani", "taxtakopir", "qoraqalpogiston"),
    Region("tortkol", "To‘rtko‘l tumani", "tortkol", "qoraqalpogiston"),
    Region("xojayli", "Xo‘jayli tumani", "xojayli", "qoraqalpogiston"),
    Region("mangit", "Mang‘it", "mangit", "qoraqalpogiston"),
    Region("Qo'ng'irоt", "Qo‘ng‘irot shahri", "kungirot-shahri", "qoraqalpogiston"),
    Region("Chimbоy", "Chimboy shahri", "chimboy-shahri", "qoraqalpogiston"),
    Region("xojayli-shahri", "Xo‘jayli shahri", "xojayli-shahri", "qoraqalpogiston"),
)

_REGIONS_BY_CODE = {region.code: region for region in UZBEKISTAN_REGIONS}
_REGION_GROUPS_BY_CODE = {group.code: group for group in UZBEKISTAN_REGION_GROUPS}
_REGIONS_BY_GROUP = {
    group.code: tuple(region for region in UZBEKISTAN_REGIONS if region.group_code == group.code)
    for group in UZBEKISTAN_REGION_GROUPS
}


def list_regions(*, group_code: str | None = None) -> tuple[Region, ...]:
    """Return all regions or the locations belonging to one UI group."""

    if group_code is None:
        return UZBEKISTAN_REGIONS
    get_region_group(group_code)
    return _REGIONS_BY_GROUP[group_code]


def list_region_groups() -> tuple[RegionGroup, ...]:
    """Return geographic groups in their UI order."""

    return UZBEKISTAN_REGION_GROUPS


def get_region(code: str) -> Region:
    """Resolve a stable saved region code or raise a typed error."""

    try:
        return _REGIONS_BY_CODE[code]
    except KeyError as exc:
        raise UnsupportedRegionError(f"Hudud qo‘llab-quvvatlanmaydi: {code}") from exc


def get_region_group(code: str) -> RegionGroup:
    """Resolve a geographic group or raise a typed error."""

    try:
        return _REGION_GROUPS_BY_CODE[code]
    except KeyError as exc:
        raise UnsupportedRegionError(f"Hudud guruhi qo‘llab-quvvatlanmaydi: {code}") from exc
