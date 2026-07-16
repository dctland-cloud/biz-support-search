from datetime import date

from collector.normalize import classify_period, classify_period_kstartup, REGIONS, extract_regions_from_hashtags, split_region_token

TODAY = date(2026, 7, 16)


def test_date_range_open():
    assert classify_period("2026-07-14 ~ 2026-07-27", TODAY) == ("OPEN", "2026-07-14", "2026-07-27")


def test_date_range_upcoming():
    assert classify_period("2026-08-01 ~ 2026-08-31", TODAY)[0] == "UPCOMING"


def test_date_range_closed():
    assert classify_period("2026-06-01 ~ 2026-06-30", TODAY)[0] == "CLOSED"


def test_rolling_phrases():
    for text in ["상시 접수", "예산 소진시까지", "선착순 접수", "수시 모집", "정원 마감시까지", "모집 완료시"]:
        assert classify_period(text, TODAY) == ("ROLLING", None, None), text


def test_unknown_phrases():
    for text in ["차수별 상이", "세부사업별 상이", "", None]:
        assert classify_period(text, TODAY) == ("UNKNOWN", None, None)


def test_kstartup_dates_open():
    assert classify_period_kstartup("20260710", "20260818", TODAY) == ("OPEN", "2026-07-10", "2026-08-18")


def test_kstartup_dates_missing():
    assert classify_period_kstartup(None, None, TODAY) == ("UNKNOWN", None, None)
    assert classify_period_kstartup("2026071", "20260818", TODAY) == ("UNKNOWN", None, None)


def test_split_region_simple():
    assert split_region_token("충북") == ["충북"]
    assert split_region_token("전국") == ["전국"]
    assert split_region_token("충청북도") == ["충북"]


def test_split_region_combined():
    assert split_region_token("전남광주") == ["전남", "광주"]


def test_split_region_non_region():
    assert split_region_token("박람회") == []
    assert split_region_token("") == []


def test_hashtags_regions():
    tags = "내수,충북,제천한방천연물산업박람회,2026,충청북도"
    assert extract_regions_from_hashtags(tags) == ["충북"]


def test_hashtags_combined_region():
    tags = "금융,부산,대구,전남광주,울산"
    assert extract_regions_from_hashtags(tags) == ["부산", "대구", "전남", "광주", "울산"]


def test_hashtags_no_region():
    assert extract_regions_from_hashtags("수출,바우처") == ["UNKNOWN"]
    assert extract_regions_from_hashtags(None) == ["UNKNOWN"]


def test_hashtags_all_17_regions_is_nationwide():
    assert extract_regions_from_hashtags(",".join(REGIONS)) == ["전국"]
