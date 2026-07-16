from datetime import date

from collector.normalize import classify_period, classify_period_kstartup, REGIONS, extract_regions_from_hashtags, split_region_token, map_category, strip_html

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


def test_map_category_bizinfo():
    assert map_category("bizinfo", "금융") == "자금"
    assert map_category("bizinfo", "기술") == "R&D"
    assert map_category("bizinfo", "내수") == "수출·판로"
    assert map_category("bizinfo", "제도") == "기타"


def test_map_category_kstartup():
    assert map_category("kstartup", "멘토링ㆍ컨설팅ㆍ교육") == "교육·컨설팅"
    assert map_category("kstartup", "사업화") == "창업·사업화"
    assert map_category("kstartup", "융자") == "자금"


def test_map_category_unknown_value():
    assert map_category("kstartup", "새로생긴분류") == "기타"
    assert map_category("bizinfo", None) == "기타"


def test_strip_html():
    html = '<p>공고문&nbsp;안내</p><p style="a">테스트 &#40;추경&#41;</p>'
    assert strip_html(html) == "공고문 안내 테스트 (추경)"


def test_strip_html_limit():
    assert len(strip_html("가" * 500, limit=300)) == 300
