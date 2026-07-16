from datetime import date

from collector.normalize import classify_period, classify_period_kstartup

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
