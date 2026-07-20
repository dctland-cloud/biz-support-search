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

from collector.judge import to_record_wbiz


def _wbiz_item(**kw):
    base = {
        "nttId": "1018",
        "title": "(재)여성기업종합지원센터 경남센터 제2차 입주기업 모집 공고(∼8.12까지)",
        "category": "BI입주기업",
        "period_text": "2026.07.14 (월) 00:00 ~ 2026.08.12 (수) 18:00까지",
        "method": "이메일 접수(wslee@wbiz.or.kr)",
    }
    base.update(kw)
    return base


def test_wbiz_record_basic():
    r = to_record_wbiz(_wbiz_item(), TODAY)
    assert r["id"] == "wbiz:1018"
    assert r["source"] == "wbiz"
    assert r["org"] == "여성기업종합지원센터"
    assert r["target_types"] == ["여성기업"]
    assert r["regions"] == ["경남"]
    assert r["category"] == "시설·공간"          # BI입주기업 → 시설·공간
    assert r["period_status"] == "OPEN"
    assert r["apply_start"] == "2026-07-14"
    assert r["apply_end"] == "2026-08-12"
    assert r["listed_at"] == "2026-07-14"
    assert r["eligibility_complete"] is False
    assert r["startup_years"] is None
    assert r["age_limit"] is None
    assert r["url"] == "https://wbiz.or.kr/notice/bizNewDetail.do?nttId=1018"
    assert "신청방법" in r["summary"] and "wslee@wbiz.or.kr" in r["summary"]


def test_wbiz_record_rolling_no_region():
    item = _wbiz_item(nttId="900", title="2026년 제27회 여성창업경진대회 서류 평가 결과 안내",
                      category="지원사업", period_text="2026.05.19 (화) ~ 상시모집", method="-")
    r = to_record_wbiz(item, TODAY)
    assert r["period_status"] == "ROLLING"
    assert r["regions"] == ["UNKNOWN"]
    assert r["category"] == "창업·사업화"        # 지원사업 → 창업·사업화
    assert r["summary"] is None                  # 신청방법이 '-'면 요약 생략
    assert r["apply_start"] is None and r["listed_at"] is None


def test_merge_bizinfo_with_wbiz_adds_women_tag():
    biz = _rec(id="bizinfo:1", title="(재)여성기업종합지원센터 경남센터 제2차 입주기업 모집 공고",
               apply_start="2026-07-14", apply_end="2026-08-12", url="https://bizinfo")
    wbiz = to_record_wbiz(_wbiz_item(title="(재)여성기업종합지원센터 경남센터 제2차 입주기업 모집 공고"), TODAY)
    merged = merge_duplicates([biz, wbiz])
    assert len(merged) == 1
    m = merged[0]
    assert m["source"] == "merged"
    assert "여성기업" in m["target_types"] and "중소기업" in m["target_types"]
    assert m["url"] == "https://bizinfo"
    assert m["alt_url"] == "https://wbiz.or.kr/notice/bizNewDetail.do?nttId=1018"


def test_normalize_title_strips_curly_quotes():
    # Curly quotes: U+201C U+201D U+2018 U+2019
    curly_text = '“테스트” ‘공고’'
    straight_text = '"테스트" \'공고\''
    assert normalize_title(curly_text) == normalize_title(straight_text)

    curly_test = '“테스트”'
    straight_test = "테스트"
    assert normalize_title(curly_test) == normalize_title(straight_test)
