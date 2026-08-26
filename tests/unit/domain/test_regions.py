import pytest

from namoz_bot.domain.errors import UnsupportedRegionError
from namoz_bot.domain.regions import DEFAULT_REGION_CODE, get_region, list_regions


def test_default_region_is_supported_tashkent() -> None:
    region = get_region(DEFAULT_REGION_CODE)

    assert region.code == "Toshkent"
    assert region.display_name == "Toshkent"


def test_catalog_has_unique_api_codes_and_display_names() -> None:
    regions = list_regions()

    assert len(regions) >= 70
    assert len({region.code for region in regions}) == len(regions)
    assert len({region.display_name for region in regions}) == len(regions)


def test_catalog_excludes_non_uzbekistan_locations() -> None:
    display_names = {region.display_name for region in list_regions()}

    assert display_names.isdisjoint(
        {"Bishkek", "Dushanbe", "Chimkent", "Osh", "Xo‘jand", "Olmaota"}
    )


def test_display_name_maps_to_exact_islomapi_code() -> None:
    region = next(item for item in list_regions() if item.display_name == "Farg‘ona")

    assert region.code == "Farg'\u043ena"


def test_unknown_region_is_rejected() -> None:
    with pytest.raises(UnsupportedRegionError, match="qo‘llab-quvvatlanmaydi"):
        get_region("Unknown")
