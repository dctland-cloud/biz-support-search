import json
from datetime import date
from pathlib import Path

from collector.judge import to_record_bizinfo, to_record_kstartup

TODAY = date(2026, 7, 16)
FIXTURES = Path(__file__).parent.parent / "references" / "phase0"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_bizinfo_record_basic():
    item = _load("bizinfo_sample3.json")[0]  # 제천한방천연물산업박람회
    r = to_record_bizinfo(item, TODAY)
    assert r["id"] == "bizinfo:PBLN_000000000124403"
    assert r["source"] == "bizinfo"
    assert r["regions"] == ["충북"]
    assert r["target_types"] == ["중소기업"]
    assert r["category"] == "수출·판로"          # 내수 → 수출·판로
    assert r["period_status"] == "OPEN"
    assert r["apply_end"] == "2026-07-27"
    assert r["eligibility_complete"] is False
    assert r["startup_years"] is None
    assert r["listed_at"] == "2026-07-15"
    assert "<p>" not in r["summary"]
    assert r["title"] == "[충북] 2026년 제천한방천연물산업박람회 체험ㆍ플리마켓 참가자 모집 공고"
    assert r["org"] == "충청북도 · 제천한방천연물산업진흥재단"
    assert r["raw_category"] == "내수"
    assert r["apply_start"] == "2026-07-14"
    assert r["raw_period_text"] == "2026-07-14 ~ 2026-07-27"


def test_bizinfo_rolling_record():
    item = _load("bizinfo_sample3.json")[1]  # 예산 소진시까지
    r = to_record_bizinfo(item, TODAY)
    assert r["period_status"] == "ROLLING"
    assert r["apply_end"] is None


def test_bizinfo_combined_region():
    item = _load("bizinfo_sample3.json")[2]  # hashtags에 전남광주 포함
    r = to_record_bizinfo(item, TODAY)
    assert "전남" in r["regions"] and "광주" in r["regions"]
    assert r["alt_url"] == "http://a.to/26jyUIr"


def test_kstartup_record_basic():
    item = _load("kstartup_sample3.json")[2]  # 대구 콘텐츠 지원
    r = to_record_kstartup(item, TODAY)
    assert r["id"] == "kstartup:178508"
    assert r["source"] == "kstartup"
    assert r["regions"] == ["대구"]
    assert r["target_types"] == ["일반기업", "1인 창조기업"]
    assert r["startup_years"][0] == "예비창업자"
    assert len(r["age_limit"]) == 3
    assert r["eligibility_complete"] is True
    assert r["period_status"] == "OPEN"
    assert r["listed_at"] == "2026-07-10"
    assert r["url"].startswith("https://www.k-startup.go.kr")
    assert r["category"] == "창업·사업화"
    assert r["summary"]
    assert "<" not in r["summary"]
    assert r["raw_period_text"] == "20260710 ~ 20260721"
