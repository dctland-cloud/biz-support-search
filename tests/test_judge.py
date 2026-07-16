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


from collector.judge import merge_duplicates, normalize_title


def _rec(**kw):
    base = {
        "id": "bizinfo:X", "title": "테스트 공고", "summary": "", "source": "bizinfo",
        "org": "기관A", "category": "기타", "raw_category": None,
        "regions": ["전국"], "target_types": ["중소기업"],
        "startup_years": None, "age_limit": None,
        "period_status": "OPEN", "apply_start": "2026-07-01", "apply_end": "2026-07-31",
        "listed_at": "2026-07-01", "eligibility_complete": False,
        "url": "https://a", "alt_url": None, "raw_period_text": "",
    }
    base.update(kw)
    return base


def test_normalize_title():
    assert normalize_title("[충북] 2026년 테스트 (추경) 공고") == normalize_title("[충북]2026년테스트(추경)공고")
    assert normalize_title(None) == ""


def test_merge_same_title_and_period():
    a = _rec(id="bizinfo:1", url="https://bizinfo")
    b = _rec(id="kstartup:1", source="kstartup", url="https://kstartup",
             startup_years=["예비창업자"], age_limit=["만 40세 이상"],
             eligibility_complete=True, target_types=["일반기업"], org="기관B")
    merged = merge_duplicates([a, b])
    assert len(merged) == 1
    m = merged[0]
    assert m["source"] == "merged"
    assert m["url"] == "https://bizinfo"
    assert m["alt_url"] == "https://kstartup"
    assert m["startup_years"] == ["예비창업자"]      # kstartup 구조화 필드 이식
    assert m["eligibility_complete"] is True
    assert set(m["target_types"]) == {"중소기업", "일반기업"}


def test_no_merge_different_period():
    a = _rec(id="bizinfo:1")
    b = _rec(id="kstartup:1", source="kstartup", apply_end="2026-08-15")
    assert len(merge_duplicates([a, b])) == 2


def test_no_merge_empty_title():
    a = _rec(id="bizinfo:1", title="")
    b = _rec(id="kstartup:1", source="kstartup", title="")
    assert len(merge_duplicates([a, b])) == 2

def test_normalize_title_strips_curly_quotes():
    # Curly quotes: U+201C U+201D U+2018 U+2019
    curly_text = '“테스트” ‘공고’'
    straight_text = '"테스트" \'공고\''
    assert normalize_title(curly_text) == normalize_title(straight_text)

    curly_test = '“테스트”'
    straight_test = "테스트"
    assert normalize_title(curly_test) == normalize_title(straight_test)
