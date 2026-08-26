import pytest

import namoz_bot.domain.regions as regions_module
from namoz_bot.domain.errors import UnsupportedRegionError
from namoz_bot.domain.regions import DEFAULT_REGION_CODE, get_region, list_regions


def test_catalog_exposes_fourteen_geographic_groups_in_ui_order() -> None:
    list_region_groups = getattr(regions_module, "list_region_groups", lambda: ())

    assert [group.display_name for group in list_region_groups()] == [
        "Toshkent shahri",
        "Toshkent viloyati",
        "Sirdaryo viloyati",
        "Jizzax viloyati",
        "Samarqand viloyati",
        "Namangan viloyati",
        "Farg‘ona viloyati",
        "Andijon viloyati",
        "Buxoro viloyati",
        "Navoiy viloyati",
        "Qashqadaryo viloyati",
        "Surxondaryo viloyati",
        "Xorazm viloyati",
        "Qoraqalpog‘iston Respublikasi",
    ]


def test_default_region_is_supported_tashkent() -> None:
    region = get_region(DEFAULT_REGION_CODE)

    assert region.code == "Toshkent"
    assert region.display_name == "Toshkent shahri"
    assert region.provider_key == "toshkent-shahri"


def test_catalog_has_unique_api_codes_and_display_names() -> None:
    regions = list_regions()

    assert len(regions) >= 70
    assert len({region.code for region in regions}) == len(regions)
    assert len({region.display_name for region in regions}) == len(regions)


def test_catalog_contains_every_grouped_api_location() -> None:
    regions = list_regions()

    assert len(regions) == 223
    assert len({region.code for region in regions}) == 223
    assert len({region.provider_key for region in regions}) == 209


def test_regions_can_be_filtered_by_geographic_group() -> None:
    toshkent_city = list_regions(group_code="toshkent-shahri")
    qoraqalpogiston = list_regions(group_code="qoraqalpogiston")

    assert len(toshkent_city) == 13
    assert toshkent_city[0].display_name == "Toshkent shahri"
    assert len(qoraqalpogiston) == 23
    assert qoraqalpogiston[0].display_name == "Qoraqalpog‘iston Respublikasi"


def test_catalog_excludes_non_uzbekistan_locations() -> None:
    display_names = {region.display_name for region in list_regions()}

    assert display_names.isdisjoint(
        {"Bishkek", "Dushanbe", "Chimkent", "Osh", "Xo‘jand", "Olmaota"}
    )


def test_stable_region_code_maps_to_exact_provider_slug() -> None:
    region = next(item for item in list_regions() if item.display_name == "Farg‘ona shahri")

    assert region.code == "Farg'\u043ena"
    assert region.provider_key == "fargona-shahri"


def test_known_district_alias_uses_provider_canonical_slug() -> None:
    region = next(item for item in list_regions() if item.display_name == "Andijon tumani")

    assert region.code == "andijon"
    assert region.provider_key == "andijon-shahri"


def test_unknown_region_is_rejected() -> None:
    with pytest.raises(UnsupportedRegionError, match="qo‘llab-quvvatlanmaydi"):
        get_region("Unknown")
