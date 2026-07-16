# biz-support-search Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기업마당 + K-Startup 공고를 매일 자동 수집해 정적 검색 웹앱(GitHub Pages)으로 제공한다.

**Architecture:** Python 수집기가 두 공식 API를 호출해 정규화·판정·병합 후 `site/data/programs.json`을 생성한다. GitHub Actions가 매일 05:00 KST에 수집기를 실행해 데이터를 커밋하고 `site/`를 GitHub Pages로 배포한다. 검색·필터링은 사용자 브라우저에서 순수 JS로 수행한다(서버 없음).

**Tech Stack:** Python 3.11+ (requests만 사용), pytest, 순수 HTML/CSS/JS, GitHub Actions, GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-07-16-biz-support-search-design.md`

## Global Constraints

- 인증키(`BIZINFO_CRTFC_KEY`)는 코드·저장소에 절대 포함 금지. 로컬은 `~/.biz-support-search/.env`, CI는 GitHub Actions Secrets만 사용.
- 공식 API만 사용. HTML 크롤링 금지. 같은 호스트 연속 호출 사이 1초 대기. User-Agent 명시: `biz-support-search/1.0 (+https://github.com/dctland-cloud/biz-support-search)`
- 기업마당 응답은 HTTP 200이어도 본문에 `reqErr` 키가 있으면 실패로 처리. `totCnt == fetched` 검증 필수. K-Startup은 `matchCount == 수집 건수` 검증 필수.
- 필수 필드(id, title, url) 누락률이 5% 초과면 해당 소스 수집 실패로 처리.
- 지역 표준값 17개: 서울 부산 대구 인천 광주 대전 울산 세종 경기 강원 충북 충남 전북 전남 경북 경남 제주. 특수값: `전국`, `UNKNOWN`.
- `period_status` 값: `OPEN` `ROLLING` `UPCOMING` `CLOSED` `UNKNOWN` (CLOSED는 최종 JSON에서 제외).
- 공통 분야(category) 9종: 자금, R&D, 수출·판로, 인력, 창업·사업화, 교육·컨설팅, 시설·공간, 행사·네트워크, 기타.
- 모든 파일 인코딩 UTF-8. 날짜는 ISO(`YYYY-MM-DD`), 기준 시간대 Asia/Seoul.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` 추가.

## 공고 레코드 스키마 (모든 태스크 공통)

```json
{
  "id": "bizinfo:PBLN_000000000124403",
  "title": "공고명",
  "summary": "HTML 제거된 요약 (최대 300자)",
  "source": "bizinfo | kstartup | merged",
  "org": "소관기관 · 수행기관",
  "category": "자금",
  "raw_category": "금융",
  "regions": ["충북"],
  "target_types": ["중소기업"],
  "startup_years": ["예비창업자", "1년미만"],
  "age_limit": ["만 20세 이상 ~ 만 39세 이하"],
  "period_status": "OPEN",
  "apply_start": "2026-07-14",
  "apply_end": "2026-07-27",
  "listed_at": "2026-07-15",
  "eligibility_complete": false,
  "url": "https://...",
  "alt_url": null,
  "raw_period_text": "2026-07-14 ~ 2026-07-27"
}
```

`startup_years`/`age_limit`은 K-Startup 전용(기업마당은 `null`). `listed_at`은 기업마당 `creatPnttm` 앞 10자, K-Startup은 `pbanc_rcpt_bgng_dt`를 ISO로 변환.

---

### Task 1: 프로젝트 골격 + 신청기간 상태 판정

**Files:**
- Create: `collector/__init__.py` (빈 파일)
- Create: `collector/normalize.py`
- Create: `tests/test_normalize.py`
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Modify: `.gitignore` (1행: `data/` → `/data/`)

**Interfaces:**
- Produces: `classify_period(text: str|None, today: date) -> tuple[str, str|None, str|None]` — (status, start_iso, end_iso)
- Produces: `classify_period_kstartup(bgng: str|None, end: str|None, today: date) -> tuple[str, str|None, str|None]`

- [ ] **Step 1: 골격 파일 생성**

`requirements.txt`:
```
requests>=2.31
tzdata>=2024.1
```
(tzdata: Windows에는 IANA 시간대 DB가 없어 `ZoneInfo("Asia/Seoul")`가 실패함 — Linux에서는 무해)

`pyproject.toml`:
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

`collector/__init__.py`: 빈 파일.

`.gitignore`에서 `data/` 행을 `/data/`로 교체 (site/data/의 생성물은 커밋해야 GitHub Pages로 서빙됨).

- [ ] **Step 2: 실패하는 테스트 작성** — `tests/test_normalize.py`

```python
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
```

- [ ] **Step 3: 실패 확인**

Run: `pytest tests/test_normalize.py -v`
Expected: FAIL — `ModuleNotFoundError` 또는 `ImportError` (classify_period 미정의)

- [ ] **Step 4: 최소 구현** — `collector/normalize.py`

```python
"""지역·기간·분야 정규화 — 소스 원본 값을 공통 표현으로 바꾼다."""
import re
from datetime import date, datetime

# Phase 0 실측 UNKNOWN 문구 중 사실상 상시 모집인 패턴을 ROLLING으로 흡수
_ROLLING_PATTERNS = (
    "상시", "수시", "예산 소진", "예산소진", "소진시", "소진 시",
    "선착순", "마감시", "마감 시", "완료시", "완료 시",
)
_DATE_RANGE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})")


def _status_from_dates(start: date, end: date, today: date) -> str:
    if today < start:
        return "UPCOMING"
    if today > end:
        return "CLOSED"
    return "OPEN"


def classify_period(text, today):
    """기업마당 신청기간 원문 → (status, start_iso, end_iso)."""
    text = (text or "").strip()
    m = _DATE_RANGE.search(text)
    if m:
        try:
            start = date.fromisoformat(m.group(1))
            end = date.fromisoformat(m.group(2))
        except ValueError:
            return ("UNKNOWN", None, None)
        return (_status_from_dates(start, end, today), start.isoformat(), end.isoformat())
    if any(p in text for p in _ROLLING_PATTERNS):
        return ("ROLLING", None, None)
    return ("UNKNOWN", None, None)


def classify_period_kstartup(bgng, end, today):
    """K-Startup YYYYMMDD 시작·마감 → (status, start_iso, end_iso)."""
    try:
        s = datetime.strptime(bgng or "", "%Y%m%d").date()
        e = datetime.strptime(end or "", "%Y%m%d").date()
    except ValueError:
        return ("UNKNOWN", None, None)
    return (_status_from_dates(s, e, today), s.isoformat(), e.isoformat())
```

- [ ] **Step 5: 통과 확인**

Run: `pytest tests/test_normalize.py -v`
Expected: 7 passed

- [ ] **Step 6: 커밋**

```bash
git add collector/ tests/ pyproject.toml requirements.txt .gitignore
git commit -m "feat: 프로젝트 골격 + 신청기간 상태 판정 (OPEN/ROLLING/UPCOMING/CLOSED/UNKNOWN)"
```

---

### Task 2: 지역 정규화

**Files:**
- Modify: `collector/normalize.py` (함수 추가)
- Modify: `tests/test_normalize.py` (테스트 추가)

**Interfaces:**
- Produces: `REGIONS: list[str]` (17개 시도)
- Produces: `split_region_token(token: str) -> list[str]` — 단일 토큰 → 표준 지역 리스트 (비지역 토큰이면 `[]`)
- Produces: `extract_regions_from_hashtags(hashtags: str|None) -> list[str]` — 항상 1개 이상 (`["UNKNOWN"]` 폴백)

- [ ] **Step 1: 실패하는 테스트 추가** — `tests/test_normalize.py`에 이어서

```python
from collector.normalize import REGIONS, extract_regions_from_hashtags, split_region_token


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
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_normalize.py -v`
Expected: 신규 7건 FAIL (ImportError)

- [ ] **Step 3: 구현** — `collector/normalize.py`에 추가

```python
REGIONS = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
]
_REGION_ALIASES = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산",
    "세종특별자치시": "세종", "경기도": "경기", "강원도": "강원", "강원특별자치도": "강원",
    "충청북도": "충북", "충청남도": "충남", "전라북도": "전북", "전북특별자치도": "전북",
    "전라남도": "전남", "경상북도": "경북", "경상남도": "경남",
    "제주도": "제주", "제주특별자치도": "제주",
}


def split_region_token(token):
    """토큰 하나를 표준 지역 리스트로. '전남광주' 같은 결합값은 분해, 비지역이면 []."""
    token = _REGION_ALIASES.get((token or "").strip(), (token or "").strip())
    if token == "전국":
        return ["전국"]
    if token in REGIONS:
        return [token]
    for i in range(2, len(token)):
        a, b = token[:i], token[i:]
        if a in REGIONS and b in REGIONS:
            return [a, b]
    return []


def extract_regions_from_hashtags(hashtags):
    """기업마당 hashtags(콤마 구분)에서 지역만 추출. 없으면 UNKNOWN, 17개 전부면 전국."""
    found = []
    for raw in (hashtags or "").split(","):
        for r in split_region_token(raw):
            if r not in found:
                found.append(r)
    if "전국" in found or len([r for r in found if r != "전국"]) >= 17:
        return ["전국"]
    return found or ["UNKNOWN"]
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_normalize.py -v`
Expected: 14 passed

- [ ] **Step 5: 커밋**

```bash
git add collector/normalize.py tests/test_normalize.py
git commit -m "feat: 지역 정규화 — 17개 시도, 별칭, 결합값(전남광주) 분해, 전국/UNKNOWN 처리"
```

---

### Task 3: 분야(category) 매핑 + HTML 요약 정리

**Files:**
- Modify: `collector/normalize.py` (함수 추가)
- Modify: `tests/test_normalize.py` (테스트 추가)

**Interfaces:**
- Produces: `map_category(source: str, raw: str|None) -> str` — 공통 분야 9종 중 하나 (미등록 값 → "기타")
- Produces: `strip_html(html: str|None, limit: int = 300) -> str`

- [ ] **Step 1: 실패하는 테스트 추가** — `tests/test_normalize.py`에 이어서

```python
from collector.normalize import map_category, strip_html


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
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_normalize.py -v`
Expected: 신규 5건 FAIL

- [ ] **Step 3: 구현** — `collector/normalize.py`에 추가

```python
import html as _html

CATEGORIES = [
    "자금", "R&D", "수출·판로", "인력", "창업·사업화",
    "교육·컨설팅", "시설·공간", "행사·네트워크", "기타",
]
_BIZINFO_CAT = {
    "금융": "자금", "기술": "R&D", "인력": "인력", "수출": "수출·판로",
    "내수": "수출·판로", "창업": "창업·사업화", "경영": "교육·컨설팅",
    "제도": "기타", "기타": "기타",
}
_KSTARTUP_CAT = {
    "융자": "자금", "정책자금": "자금", "보조금": "자금",
    "R&D": "R&D", "기술개발(R&D)": "R&D", "기술개발(R&D)ㆍ사업화": "R&D",
    "판로ㆍ해외진출": "수출·판로", "글로벌": "수출·판로", "글로벌진출": "수출·판로",
    "판로ㆍ해외진출ㆍ글로벌": "수출·판로",
    "인력": "인력", "인력양성": "인력",
    "사업화": "창업·사업화", "창업": "창업·사업화",
    "멘토링ㆍ컨설팅ㆍ교육": "교육·컨설팅", "창업교육": "교육·컨설팅",
    "시설ㆍ공간ㆍ보육": "시설·공간",
    "행사ㆍ네트워크": "행사·네트워크",
}
_TAG = re.compile(r"<[^>]+>")


def map_category(source, raw):
    table = _BIZINFO_CAT if source == "bizinfo" else _KSTARTUP_CAT
    return table.get((raw or "").strip(), "기타")


def strip_html(value, limit=300):
    text = _TAG.sub(" ", value or "")
    text = _html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]
```

(`import html as _html`은 파일 상단 import 블록으로 이동)

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_normalize.py -v`
Expected: 19 passed

- [ ] **Step 5: 커밋**

```bash
git add collector/normalize.py tests/test_normalize.py
git commit -m "feat: 공통 분야 9종 매핑 + HTML 요약 정리"
```

---

### Task 4: 원본 → 공고 레코드 변환

**Files:**
- Create: `collector/judge.py`
- Create: `tests/test_judge.py`

**Interfaces:**
- Consumes: Task 1~3의 normalize 함수 전부
- Produces: `to_record_bizinfo(item: dict, today: date) -> dict` — 공고 레코드 스키마(위 공통 절) 그대로
- Produces: `to_record_kstartup(item: dict, today: date) -> dict`
- Produces: `_split_csv(value: str|None) -> list[str]`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_judge.py`

fixture는 Phase 0 실측 샘플을 그대로 재사용한다 (`references/phase0/bizinfo_sample3.json`, `references/phase0/kstartup_sample3.json`).

```python
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


def test_bizinfo_rolling_record():
    item = _load("bizinfo_sample3.json")[1]  # 예산 소진시까지
    r = to_record_bizinfo(item, TODAY)
    assert r["period_status"] == "ROLLING"
    assert r["apply_end"] is None


def test_bizinfo_combined_region():
    item = _load("bizinfo_sample3.json")[2]  # hashtags에 전남광주 포함
    r = to_record_bizinfo(item, TODAY)
    assert "전남" in r["regions"] and "광주" in r["regions"]


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
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_judge.py -v`
Expected: FAIL (collector.judge 미존재)

- [ ] **Step 3: 구현** — `collector/judge.py`

```python
"""원본 공고 → 공통 레코드 변환, 중복 병합, 자격 판정 준비."""
from collector.normalize import (
    classify_period,
    classify_period_kstartup,
    extract_regions_from_hashtags,
    map_category,
    split_region_token,
    strip_html,
)


def _split_csv(value):
    return [t.strip() for t in (value or "").split(",") if t.strip()]


def to_record_bizinfo(item, today):
    status, start, end = classify_period(item.get("reqstBeginEndDe"), today)
    org_parts = [item.get("jrsdInsttNm"), item.get("excInsttNm")]
    created = (item.get("creatPnttm") or "")[:10]
    return {
        "id": f"bizinfo:{item.get('pblancId', '')}",
        "title": (item.get("pblancNm") or "").strip(),
        "summary": strip_html(item.get("bsnsSumryCn")),
        "source": "bizinfo",
        "org": " · ".join(dict.fromkeys(p for p in org_parts if p)),
        "category": map_category("bizinfo", item.get("pldirSportRealmLclasCodeNm")),
        "raw_category": item.get("pldirSportRealmLclasCodeNm"),
        "regions": extract_regions_from_hashtags(item.get("hashtags")),
        "target_types": _split_csv(item.get("trgetNm")),
        "startup_years": None,
        "age_limit": None,
        "period_status": status,
        "apply_start": start,
        "apply_end": end,
        "listed_at": created or None,
        "eligibility_complete": False,
        "url": item.get("pblancUrl"),
        "alt_url": item.get("rceptEngnHmpgUrl"),
        "raw_period_text": (item.get("reqstBeginEndDe") or "").strip(),
    }


def to_record_kstartup(item, today):
    bgng, end_raw = item.get("pbanc_rcpt_bgng_dt"), item.get("pbanc_rcpt_end_dt")
    status, start, end = classify_period_kstartup(bgng, end_raw, today)
    return {
        "id": f"kstartup:{item.get('pbanc_sn', '')}",
        "title": (item.get("biz_pbanc_nm") or "").strip(),
        "summary": strip_html(item.get("pbanc_ctnt")),
        "source": "kstartup",
        "org": item.get("pbanc_ntrp_nm") or item.get("sprv_inst") or "",
        "category": map_category("kstartup", item.get("supt_biz_clsfc")),
        "raw_category": item.get("supt_biz_clsfc"),
        "regions": split_region_token(item.get("supt_regin") or "") or ["UNKNOWN"],
        "target_types": _split_csv(item.get("aply_trgt")),
        "startup_years": _split_csv(item.get("biz_enyy")) or None,
        "age_limit": _split_csv(item.get("biz_trgt_age")) or None,
        "period_status": status,
        "apply_start": start,
        "apply_end": end,
        "listed_at": start,
        "eligibility_complete": True,
        "url": item.get("detl_pg_url"),
        "alt_url": item.get("aply_mthd_onli_rcpt_istc"),
        "raw_period_text": f"{bgng or ''} ~ {end_raw or ''}".strip(" ~"),
    }
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_judge.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add collector/judge.py tests/test_judge.py
git commit -m "feat: 기업마당·K-Startup 원본을 공통 공고 레코드로 변환"
```

---

### Task 5: 중복 병합

**Files:**
- Modify: `collector/judge.py` (함수 추가)
- Modify: `tests/test_judge.py` (테스트 추가)

**Interfaces:**
- Produces: `normalize_title(title: str|None) -> str`
- Produces: `merge_duplicates(records: list[dict]) -> list[dict]` — 정규화 제목+apply_start+apply_end 일치 시 병합, `source="merged"`

- [ ] **Step 1: 실패하는 테스트 추가** — `tests/test_judge.py`에 이어서

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_judge.py -v`
Expected: 신규 4건 FAIL

- [ ] **Step 3: 구현** — `collector/judge.py`에 추가

```python
import re

_TITLE_NOISE = re.compile(r"[\s\[\]()〔〕『』「」《》<>·ㆍ,.\-~〈〉""''\"']+")


def normalize_title(title):
    return _TITLE_NOISE.sub("", (title or "")).lower()


def _merge_into(base, other):
    """other(주로 kstartup)의 정보를 base에 합친다."""
    base["source"] = "merged"
    if not base.get("alt_url"):
        base["alt_url"] = other.get("url")
    for field in ("startup_years", "age_limit"):
        if base.get(field) is None:
            base[field] = other.get(field)
    if other.get("eligibility_complete"):
        base["eligibility_complete"] = True
    for t in other.get("target_types", []):
        if t not in base["target_types"]:
            base["target_types"].append(t)
    regions = [r for r in base["regions"] + other.get("regions", []) if r != "UNKNOWN"]
    deduped = list(dict.fromkeys(regions))
    base["regions"] = ["전국"] if "전국" in deduped else (deduped or ["UNKNOWN"])


def merge_duplicates(records):
    """정규화 제목 + 신청 시작일 + 마감일이 같으면 동일 공고로 병합."""
    seen = {}
    result = []
    for rec in records:
        key = (normalize_title(rec["title"]), rec["apply_start"], rec["apply_end"])
        if key[0] and key in seen:
            _merge_into(seen[key], rec)
        else:
            seen[key] = rec
            result.append(rec)
    return result
```

(`import re`는 파일 상단으로)

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_judge.py -v`
Expected: 8 passed

- [ ] **Step 5: 커밋**

```bash
git add collector/judge.py tests/test_judge.py
git commit -m "feat: 소스 간 중복 공고 병합 (정규화 제목+신청기간 키)"
```

---

### Task 6: API 수집기 (fetch)

**Files:**
- Create: `collector/fetch.py`
- Create: `tests/test_fetch.py`

**Interfaces:**
- Produces: `FetchError(Exception)`
- Produces: `validate_bizinfo(payload) -> list[dict]` — 순수 함수(네트워크 없음), 검증 실패 시 FetchError
- Produces: `validate_kstartup_page(payload: dict) -> dict`
- Produces: `fetch_bizinfo(crtfc_key: str, session=None) -> list[dict]`
- Produces: `fetch_kstartup(session=None) -> list[dict]`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_fetch.py`

검증 로직은 순수 함수로 분리해 네트워크 없이 테스트한다.

```python
import pytest

from collector.fetch import FetchError, validate_bizinfo, validate_kstartup_page


def test_bizinfo_req_err_detected():
    with pytest.raises(FetchError, match="인증키"):
        validate_bizinfo({"reqErr": "인증키를 입력해주세요."})


def test_bizinfo_totcnt_mismatch():
    items = [{"pblancId": "A", "totCnt": 5}, {"pblancId": "B", "totCnt": 5}]
    with pytest.raises(FetchError, match="totCnt"):
        validate_bizinfo({"jsonArray": items})


def test_bizinfo_ok():
    items = [{"pblancId": "A", "totCnt": 2}, {"pblancId": "B", "totCnt": 2}]
    assert validate_bizinfo({"jsonArray": items}) == items


def test_bizinfo_ok_bare_list():
    items = [{"pblancId": "A", "totCnt": 1}]
    assert validate_bizinfo(items) == items


def test_bizinfo_empty_fails():
    with pytest.raises(FetchError):
        validate_bizinfo({"jsonArray": []})


def test_kstartup_missing_field():
    with pytest.raises(FetchError, match="matchCount"):
        validate_kstartup_page({"currentCount": 1, "data": []})


def test_kstartup_ok():
    payload = {"currentCount": 1, "matchCount": 1, "data": [{"pbanc_sn": 1}]}
    assert validate_kstartup_page(payload) == payload
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_fetch.py -v`
Expected: FAIL (collector.fetch 미존재)

- [ ] **Step 3: 구현** — `collector/fetch.py`

```python
"""공식 API 호출 + 응답 검증. HTTP 200이어도 본문 오류를 반드시 검사한다."""
import time

import requests

USER_AGENT = "biz-support-search/1.0 (+https://github.com/dctland-cloud/biz-support-search)"
BIZINFO_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
KSTARTUP_URL = "https://nidapi.k-startup.go.kr/api/kisedKstartupService/v1/getAnnouncementInformation"
_HEADERS = {"User-Agent": USER_AGENT}
_TIMEOUT = 120


class FetchError(Exception):
    pass


def validate_bizinfo(payload):
    if isinstance(payload, dict):
        if "reqErr" in payload:
            raise FetchError(f"bizinfo 응답 오류: {payload['reqErr']}")
        items = payload.get("jsonArray")
    else:
        items = payload
    if not isinstance(items, list) or not items:
        raise FetchError("bizinfo: 응답에 공고 목록이 없음")
    tot = items[0].get("totCnt")
    if tot is not None and int(tot) != len(items):
        raise FetchError(f"bizinfo: totCnt {tot} != fetched {len(items)}")
    return items


def fetch_bizinfo(crtfc_key, session=None):
    s = session or requests.Session()
    resp = s.get(
        BIZINFO_URL,
        params={"crtfcKey": crtfc_key, "dataType": "json", "searchCnt": 0},
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return validate_bizinfo(resp.json())


def validate_kstartup_page(payload):
    for key in ("currentCount", "matchCount", "data"):
        if key not in payload:
            raise FetchError(f"kstartup: 응답에 {key} 없음")
    return payload


def fetch_kstartup(session=None):
    s = session or requests.Session()
    items, page = [], 1
    while True:
        resp = s.get(
            KSTARTUP_URL,
            params={
                "page": page,
                "perPage": 1000,
                "returnType": "json",
                "cond[rcrt_prgs_yn::EQ]": "Y",
            },
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        payload = validate_kstartup_page(resp.json())
        items.extend(payload["data"])
        if len(items) >= payload["matchCount"] or not payload["data"]:
            break
        page += 1
        time.sleep(1)  # 같은 호스트 예절: 페이지 사이 1초 대기
    if len(items) != payload["matchCount"]:
        raise FetchError(f"kstartup: matchCount {payload['matchCount']} != fetched {len(items)}")
    return items
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_fetch.py -v`
Expected: 7 passed

- [ ] **Step 5: 커밋**

```bash
git add collector/fetch.py tests/test_fetch.py
git commit -m "feat: 기업마당·K-Startup API 수집기 — 본문 오류·건수 검증 포함"
```

---

### Task 7: 파이프라인(build) + 로컬 실수집 1회

**Files:**
- Create: `collector/build.py`
- Create: `tests/test_build.py`

**Interfaces:**
- Consumes: `fetch.fetch_bizinfo/fetch_kstartup/FetchError`, `judge.to_record_*`, `judge.merge_duplicates`
- Produces: `load_env_key() -> str|None` — env 변수 우선, 없으면 `~/.biz-support-search/.env` 파싱
- Produces: `check_missing_rate(records: list[dict]) -> list[dict]` — 필수 필드 누락률 5% 초과 시 FetchError, 이하이면 누락 레코드만 제거
- Produces: `load_previous(source: str, data_dir: Path) -> list[dict]`
- Produces: `main() -> None` — 성공 시 site/data/programs.json + meta.json 기록, 전 소스 실패 시 exit 1

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_build.py`

```python
import json

import pytest

from collector.build import check_missing_rate, load_previous
from collector.fetch import FetchError


def _rec(i, source="bizinfo", **kw):
    base = {"id": f"{source}:{i}", "title": f"공고{i}", "url": "https://x", "source": source}
    base.update(kw)
    return base


def test_missing_rate_over_5pct_fails():
    records = [_rec(i) for i in range(19)] + [_rec(99, url=None)]  # 1/20 = 5%는 통과 경계
    assert len(check_missing_rate(records)) == 19
    records = [_rec(i) for i in range(18)] + [_rec(98, url=None), _rec(99, title="")]  # 2/20 = 10%
    with pytest.raises(FetchError):
        check_missing_rate(records)


def test_missing_rate_drops_bad_records():
    records = [_rec(1), _rec(2, url=None)] + [_rec(i) for i in range(3, 40)]
    cleaned = check_missing_rate(records)
    assert all(r["url"] for r in cleaned)


def test_load_previous_filters_by_source(tmp_path):
    data = [_rec(1, "bizinfo"), _rec(2, "kstartup"), _rec(3, "merged")]
    (tmp_path / "programs.json").write_text(json.dumps(data), encoding="utf-8")
    kept = load_previous("bizinfo", tmp_path)
    assert {r["source"] for r in kept} == {"bizinfo", "merged"}


def test_load_previous_no_file(tmp_path):
    assert load_previous("bizinfo", tmp_path) == []
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_build.py -v`
Expected: FAIL (collector.build 미존재)

- [ ] **Step 3: 구현** — `collector/build.py`

```python
"""수집 → 정규화 → 병합 → site/data/*.json 생성. 부분 실패 시 직전 데이터 유지."""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from collector import fetch
from collector.fetch import FetchError
from collector.judge import merge_duplicates, to_record_bizinfo, to_record_kstartup

KST = ZoneInfo("Asia/Seoul")
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "site" / "data"
_REQUIRED = ("id", "title", "url")


def load_env_key():
    key = os.environ.get("BIZINFO_CRTFC_KEY")
    if key:
        return key
    env_file = Path.home() / ".biz-support-search" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("BIZINFO_CRTFC_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def check_missing_rate(records):
    bad = [r for r in records if not all(r.get(f) for f in _REQUIRED)]
    if records and len(bad) / len(records) > 0.05:
        raise FetchError(f"필수 필드 누락 {len(bad)}/{len(records)}건 — 응답 구조 변화 의심")
    return [r for r in records if all(r.get(f) for f in _REQUIRED)]


def load_previous(source, data_dir=DATA_DIR):
    path = Path(data_dir) / "programs.json"
    if not path.exists():
        return []
    old = json.loads(path.read_text(encoding="utf-8"))
    return [r for r in old if r.get("source") in (source, "merged")]


def _collect(name, collect_fn):
    """소스 하나 수집. 실패하면 직전 데이터로 폴백하고 실패 표시."""
    try:
        records = check_missing_rate(collect_fn())
        return records, {"ok": True, "count": len(records), "error": None}
    except Exception as exc:  # 네트워크·검증·파싱 모두 폴백 대상
        records = load_previous(name)
        return records, {"ok": False, "count": len(records), "error": str(exc)}


def main():
    today = datetime.now(KST).date()

    def collect_bizinfo():
        key = load_env_key()
        if not key:
            raise FetchError("BIZINFO_CRTFC_KEY가 없음 (env 또는 ~/.biz-support-search/.env)")
        return [to_record_bizinfo(i, today) for i in fetch.fetch_bizinfo(key)]

    def collect_kstartup():
        return [to_record_kstartup(i, today) for i in fetch.fetch_kstartup()]

    biz_records, biz_status = _collect("bizinfo", collect_bizinfo)
    ks_records, ks_status = _collect("kstartup", collect_kstartup)

    if not biz_status["ok"] and not ks_status["ok"]:
        print(f"모든 소스 수집 실패 — bizinfo: {biz_status['error']} / kstartup: {ks_status['error']}")
        sys.exit(1)

    merged = merge_duplicates(biz_records + ks_records)
    merged = [r for r in merged if r["period_status"] != "CLOSED"]
    merged.sort(key=lambda r: (r["apply_end"] or "9999-12-31", r["title"]))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "programs.json").write_text(
        json.dumps(merged, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    meta = {
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "total": len(merged),
        "sources": {"bizinfo": biz_status, "kstartup": ks_status},
    }
    (DATA_DIR / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"완료: 총 {len(merged)}건 (bizinfo {biz_status['count']} / kstartup {ks_status['count']})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 단위 테스트 통과 확인**

Run: `pytest -v`
Expected: 전체 (19+8+7+5=39건 근처) passed

- [ ] **Step 5: 로컬 실수집 1회 (수동 검증)**

Run: `python -m collector.build`
Expected: `완료: 총 N건 (bizinfo ~1500 / kstartup ~260)` — N은 1,700~1,800 근처. `site/data/programs.json`과 `meta.json` 생성 확인:

```powershell
python -c "import json;d=json.load(open('site/data/programs.json',encoding='utf-8'));print(len(d), d[0]['id'], sum(1 for r in d if r['source']=='merged'), '건 병합')"
```
Expected: 총 건수, 첫 레코드 id, 병합 건수(0보다 크면 정상, phase0 기준 ~16건) 출력. 병합이 0건이어도 실패는 아님(그날 데이터에 따라 다름) — 그 경우 수동으로 원인 1건만 확인.

- [ ] **Step 6: 커밋** (생성된 데이터 포함)

```bash
git add collector/build.py tests/test_build.py site/data/
git commit -m "feat: 수집 파이프라인 — 부분 실패 폴백, CLOSED 제외, programs/meta.json 생성"
```

---

### Task 8: 웹 UI (site/)

**Files:**
- Create: `site/index.html`
- Create: `site/style.css`
- Create: `site/app.js`

**Interfaces:**
- Consumes: `site/data/programs.json` (레코드 스키마), `site/data/meta.json` (`generated_at`, `total`, `sources.{bizinfo,kstartup}.ok`)
- Produces: 정적 웹페이지. `matchRecord(record, filters) -> "ok" | "check" | null` (app.js 내부 — ✅/⚪/숨김)

- [ ] **Step 1: index.html 작성**

```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>정부 지원사업 찾기</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
  <h1>정부 지원사업 찾기</h1>
  <p class="sub">기업마당 + K-Startup 공고를 매일 자동 수집 · <span id="meta-info">데이터 불러오는 중…</span></p>
  <p id="source-warning" class="warning" hidden></p>
</header>

<section class="filters" aria-label="검색 조건">
  <div class="filter-row">
    <label>지역
      <select id="f-region"><option value="">전체</option></select>
    </label>
    <label>창업 단계(업력)
      <select id="f-stage">
        <option value="">무관</option>
        <option value="예비창업자">예비창업 (사업자 없음)</option>
        <option value="1년미만">1년 미만</option>
        <option value="2년미만">1~2년</option>
        <option value="3년미만">2~3년</option>
        <option value="5년미만">3~5년</option>
        <option value="7년미만">5~7년</option>
        <option value="10년미만">7~10년</option>
        <option value="10년이상">10년 이상</option>
      </select>
    </label>
    <label>대표자 연령
      <select id="f-age">
        <option value="">무관</option>
        <option value="youth">만 39세 이하 (청년)</option>
        <option value="over40">만 40세 이상</option>
      </select>
    </label>
    <label>정렬
      <select id="f-sort">
        <option value="deadline">마감 임박순</option>
        <option value="latest">최신 등록순</option>
      </select>
    </label>
  </div>
  <div class="filter-row"><span class="chip-label">분야</span><div id="f-category" class="chips"></div></div>
  <div class="filter-row"><span class="chip-label">대상</span><div id="f-targets" class="chips"></div></div>
  <div class="filter-row">
    <input type="search" id="f-keyword" placeholder="공고명·내용 검색 (예: 바우처, 수출)">
  </div>
</section>

<section aria-live="polite">
  <p id="result-count"></p>
  <ul id="results" class="cards"></ul>
  <button id="more" hidden>더 보기</button>
</section>

<footer>
  <p>본 서비스는 공고를 요약·분류한 것으로, 정확한 자격요건은 반드시 원문 공고를 확인하세요.</p>
  <p>출처: <a href="https://www.bizinfo.go.kr" target="_blank" rel="noopener">기업마당</a> ·
     <a href="https://www.k-startup.go.kr" target="_blank" rel="noopener">K-Startup</a></p>
</footer>
<script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: style.css 작성**

```css
* { box-sizing: border-box; }
body { margin: 0; font-family: "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
       background: #f5f6f8; color: #1c1e21; line-height: 1.5; }
header, .filters, section, footer { max-width: 860px; margin: 0 auto; padding: 12px 16px; }
header h1 { margin: 16px 0 4px; font-size: 1.5rem; }
.sub { color: #555; font-size: .85rem; margin: 0; }
.warning { background: #fff3cd; border: 1px solid #ffe08a; padding: 8px 12px;
           border-radius: 8px; font-size: .85rem; }
.filters { background: #fff; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,.08);
           margin-top: 12px; }
.filter-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 8px 0; }
.filter-row label { display: flex; flex-direction: column; font-size: .78rem; color: #666; gap: 2px; }
select, input[type=search] { padding: 8px 10px; border: 1px solid #d0d3d8; border-radius: 8px;
                             font-size: .95rem; background: #fff; }
input[type=search] { width: 100%; }
.chip-label { font-size: .78rem; color: #666; min-width: 30px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { border: 1px solid #d0d3d8; background: #fff; border-radius: 999px;
        padding: 5px 12px; font-size: .85rem; cursor: pointer; }
.chip.on { background: #1a56db; border-color: #1a56db; color: #fff; }
#result-count { font-size: .9rem; color: #444; }
.cards { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
.card { background: #fff; border-radius: 12px; padding: 14px 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.card h2 { font-size: 1.02rem; margin: 0 0 6px; }
.card h2 a { color: #1a3e8c; text-decoration: none; }
.card h2 a:hover { text-decoration: underline; }
.badges { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }
.badge { font-size: .74rem; padding: 2px 8px; border-radius: 999px; background: #eef1f5; color: #444; }
.badge.dday { background: #fde8e8; color: #c81e1e; font-weight: 700; }
.badge.rolling { background: #e1effe; color: #1a56db; }
.badge.ok { background: #def7ec; color: #046c4e; font-weight: 700; }
.badge.checkmark { background: #f3f4f6; color: #555; }
.card .meta { font-size: .8rem; color: #777; }
.card .summary { font-size: .86rem; color: #333; margin: 6px 0 0;
                 display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
#more { display: block; margin: 16px auto; padding: 10px 28px; border-radius: 999px;
        border: 1px solid #d0d3d8; background: #fff; font-size: .95rem; cursor: pointer; }
footer { color: #888; font-size: .78rem; padding-bottom: 40px; }
@media (max-width: 600px) { .filter-row label { flex: 1 1 45%; } select { width: 100%; } }
```

- [ ] **Step 3: app.js 작성**

```javascript
"use strict";

const REGIONS = ["서울","부산","대구","인천","광주","대전","울산","세종",
  "경기","강원","충북","충남","전북","전남","경북","경남","제주"];
const CATEGORIES = ["자금","R&D","수출·판로","인력","창업·사업화",
  "교육·컨설팅","시설·공간","행사·네트워크","기타"];
const PAGE_SIZE = 30;

const state = {
  records: [],
  filters: { region: "", stage: "", age: "", categories: new Set(), targets: new Set(), keyword: "", sort: "deadline" },
  shown: PAGE_SIZE,
};

function ageMatch(sel, ageLimit) {
  if (sel === "youth") return ageLimit.some(t => t.includes("39세 이하") || t.includes("20세 미만"));
  if (sel === "over40") return ageLimit.some(t => t.includes("40세 이상"));
  return true;
}

// 반환: "ok"(✅ 신청 가능) | "check"(⚪ 확인 필요) | null(조건 불일치 → 숨김)
function matchRecord(r, f) {
  let complete = r.eligibility_complete;
  if (f.region) {
    if (r.regions.includes("UNKNOWN")) complete = false;
    else if (!r.regions.includes("전국") && !r.regions.includes(f.region)) return null;
  }
  if (f.stage) {
    if (!r.startup_years) complete = false;
    else if (!r.startup_years.includes(f.stage)) return null;
  }
  if (f.age) {
    if (!r.age_limit) complete = false;
    else if (!ageMatch(f.age, r.age_limit)) return null;
  }
  if (f.targets.size) {
    if (!r.target_types.length) complete = false;
    else if (![...f.targets].some(t => r.target_types.includes(t))) return null;
  }
  if (f.categories.size && !f.categories.has(r.category)) return null;
  if (f.keyword) {
    const k = f.keyword.toLowerCase();
    const hay = (r.title + " " + (r.summary || "")).toLowerCase();
    if (!hay.includes(k)) return null;
  }
  return complete ? "ok" : "check";
}

function dday(r) {
  if (!r.apply_end) return null;
  const end = new Date(r.apply_end + "T23:59:59+09:00");
  return Math.floor((end - Date.now()) / 86400000);
}

function sortRecords(list, mode) {
  const copy = [...list];
  if (mode === "latest") {
    copy.sort((a, b) => (b.rec.listed_at || "").localeCompare(a.rec.listed_at || ""));
  } else {
    copy.sort((a, b) => {
      const ka = a.rec.apply_end || "9999-12-31", kb = b.rec.apply_end || "9999-12-31";
      return ka === kb ? a.rec.title.localeCompare(b.rec.title, "ko") : ka.localeCompare(kb);
    });
  }
  return copy;
}

function esc(s) {
  return (s || "").replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function cardHtml({ rec, verdict }) {
  const d = dday(rec);
  const badges = [];
  if (verdict === "ok") badges.push('<span class="badge ok">✅ 신청 가능</span>');
  else badges.push('<span class="badge checkmark">⚪ 원문 확인 필요</span>');
  if (rec.period_status === "ROLLING") badges.push('<span class="badge rolling">상시 모집</span>');
  else if (rec.period_status === "UPCOMING") badges.push('<span class="badge">접수 예정</span>');
  else if (d !== null && d >= 0) badges.push(`<span class="badge dday">D-${d === 0 ? "DAY" : d}</span>`);
  else if (rec.period_status === "UNKNOWN") badges.push('<span class="badge">기간 원문 확인</span>');
  badges.push(`<span class="badge">${esc(rec.category)}</span>`);
  rec.regions.filter(x => x !== "UNKNOWN").slice(0, 3)
    .forEach(x => badges.push(`<span class="badge">${esc(x)}</span>`));
  const period = rec.apply_end
    ? `${rec.apply_start || "?"} ~ ${rec.apply_end}`
    : esc(rec.raw_period_text || "기간 원문 확인");
  return `<li class="card">
    <div class="badges">${badges.join("")}</div>
    <h2><a href="${esc(rec.url)}" target="_blank" rel="noopener">${esc(rec.title)}</a></h2>
    <p class="meta">${esc(rec.org)} · ${period}</p>
    ${rec.summary ? `<p class="summary">${esc(rec.summary)}</p>` : ""}
  </li>`;
}

function render() {
  const f = state.filters;
  const matched = [];
  for (const rec of state.records) {
    const verdict = matchRecord(rec, f);
    if (verdict) matched.push({ rec, verdict });
  }
  const sorted = sortRecords(matched, f.sort);
  const okCount = sorted.filter(m => m.verdict === "ok").length;
  document.getElementById("result-count").textContent =
    `${sorted.length}건 (✅ 신청 가능 ${okCount} · ⚪ 확인 필요 ${sorted.length - okCount})`;
  document.getElementById("results").innerHTML =
    sorted.slice(0, state.shown).map(cardHtml).join("");
  document.getElementById("more").hidden = sorted.length <= state.shown;
}

function buildChips(containerId, values, selectedSet) {
  const box = document.getElementById(containerId);
  box.innerHTML = values.map(v => `<button type="button" class="chip" data-v="${esc(v)}">${esc(v)}</button>`).join("");
  box.addEventListener("click", e => {
    const btn = e.target.closest(".chip");
    if (!btn) return;
    const v = btn.dataset.v;
    if (selectedSet.has(v)) { selectedSet.delete(v); btn.classList.remove("on"); }
    else { selectedSet.add(v); btn.classList.add("on"); }
    state.shown = PAGE_SIZE;
    render();
  });
}

function init(records, meta) {
  state.records = records;
  const metaEl = document.getElementById("meta-info");
  metaEl.textContent = `데이터 기준: ${meta.generated_at.replace("T", " ").slice(0, 16)}`;
  const failed = Object.entries(meta.sources).filter(([, s]) => !s.ok).map(([n]) => n);
  if (failed.length) {
    const warn = document.getElementById("source-warning");
    warn.textContent = `일부 출처(${failed.join(", ")})의 최신 갱신에 실패해 이전 데이터가 포함되어 있어요.`;
    warn.hidden = false;
  }
  const regionSel = document.getElementById("f-region");
  REGIONS.forEach(r => regionSel.insertAdjacentHTML("beforeend", `<option>${r}</option>`));
  buildChips("f-category", CATEGORIES, state.filters.categories);
  const targetCount = new Map();
  records.forEach(r => r.target_types.forEach(t => targetCount.set(t, (targetCount.get(t) || 0) + 1)));
  const topTargets = [...targetCount.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([t]) => t);
  buildChips("f-targets", topTargets, state.filters.targets);

  const bind = (id, key) => document.getElementById(id).addEventListener("change", e => {
    state.filters[key] = e.target.value; state.shown = PAGE_SIZE; render();
  });
  bind("f-region", "region"); bind("f-stage", "stage"); bind("f-age", "age"); bind("f-sort", "sort");
  document.getElementById("f-keyword").addEventListener("input", e => {
    state.filters.keyword = e.target.value.trim(); state.shown = PAGE_SIZE; render();
  });
  document.getElementById("more").addEventListener("click", () => {
    state.shown += PAGE_SIZE; render();
  });
  render();
}

Promise.all([
  fetch("data/programs.json").then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }),
  fetch("data/meta.json").then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }),
]).then(([records, meta]) => init(records, meta))
  .catch(err => {
    document.getElementById("meta-info").textContent = "데이터를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.";
    console.error(err);
  });
```

- [ ] **Step 4: 로컬 브라우저 검증**

Run: `python -m http.server 8765 --directory site` (백그라운드)
브라우저(agent-browser 또는 playwright)로 `http://localhost:8765` 접속해 확인:
- 총 건수가 Task 7 수집 건수와 일치
- 지역 "대구" 선택 → 대구·전국 공고만 남음
- 창업 단계 "예비창업 (사업자 없음)" 선택 → ✅ 카드가 존재하고 전부 K-Startup/merged 공고
- 키워드 "수출" 입력 → 건수 감소, 카드 제목·요약에 수출 포함
- 정렬 "마감 임박순"에서 첫 카드의 D-day가 가장 작음
- 모바일 폭(375px)에서 필터가 세로로 정렬됨
확인 후 서버 종료.

- [ ] **Step 5: 커밋**

```bash
git add site/index.html site/style.css site/app.js
git commit -m "feat: 검색 웹 UI — 조건 필터, 자격 2단계 표시, D-day, 키워드 검색"
```

---

### Task 9: GitHub 저장소 + Actions 자동화 + Pages 배포

**Files:**
- Create: `.github/workflows/collect.yml`
- Create: `README.md`

**Interfaces:**
- Consumes: `python -m collector.build` (Task 7), `site/` (Task 8), GitHub Secrets `BIZINFO_CRTFC_KEY`

- [ ] **Step 1: 워크플로 작성** — `.github/workflows/collect.yml`

```yaml
name: collect-and-deploy

on:
  schedule:
    - cron: "0 20 * * *"   # 매일 05:00 KST
  workflow_dispatch:
  push:
    branches: [master]

permissions:
  contents: write
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install deps and run tests
        run: |
          pip install -r requirements.txt pytest
          pytest -q

      - name: Collect data
        env:
          BIZINFO_CRTFC_KEY: ${{ secrets.BIZINFO_CRTFC_KEY }}
        run: python -m collector.build

      - name: Commit refreshed data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add site/data
          if git diff --cached --quiet; then
            echo "데이터 변경 없음 — 커밋 생략"
          else
            git commit -m "data: daily refresh"
            git push
          fi

      - uses: actions/configure-pages@v5
        with:
          enablement: true

      - uses: actions/upload-pages-artifact@v3
        with:
          path: site

      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: README.md 작성**

```markdown
# 정부 지원사업 찾기 (biz-support-search)

기업마당 + K-Startup 공고를 매일 새벽 5시(KST)에 자동 수집해,
조건(지역·업력·연령·대상·분야)을 선택하면 신청 가능한 공고만 보여주는 검색 웹앱.

- 사이트: https://dctland-cloud.github.io/biz-support-search/
- 설계: `docs/superpowers/specs/2026-07-16-biz-support-search-design.md`
- 소스 실측: `references/phase0/phase0-report.md`

## 로컬 실행

```
pip install -r requirements.txt
python -m collector.build      # 수집 (키: ~/.biz-support-search/.env)
python -m http.server 8765 --directory site
```

## 주의

인증키는 커밋 금지 — 로컬 `~/.biz-support-search/.env`, CI는 Actions Secrets.
```

- [ ] **Step 3: 저장소 생성 + 푸시**

```bash
gh repo create biz-support-search --public --source . --remote origin --push
```
Expected: `https://github.com/dctland-cloud/biz-support-search` 생성, master 푸시 완료.

- [ ] **Step 4: Secrets 등록** (키 값은 로컬 .env에서 읽어 전달 — 화면에 출력 금지)

PowerShell:
```powershell
$line = Get-Content "$env:USERPROFILE\.biz-support-search\.env" | Where-Object { $_ -match '^BIZINFO_CRTFC_KEY=' }
$key = ($line -split '=', 2)[1].Trim().Trim('"')
$key | gh secret set BIZINFO_CRTFC_KEY --repo dctland-cloud/biz-support-search
```
Expected: `✓ Set Actions secret BIZINFO_CRTFC_KEY`

- [ ] **Step 5: 커밋 + 푸시 + 워크플로 실행**

```bash
git add .github/ README.md
git commit -m "ci: 매일 자동 수집 + GitHub Pages 배포 워크플로"
git push
gh run watch --exit-status
```
Expected: push 트리거로 워크플로 실행 → tests pass → collect → deploy 성공 (exit 0).

- [ ] **Step 6: 배포 검증**

브라우저로 `https://dctland-cloud.github.io/biz-support-search/` 접속:
- 페이지 로드, 총 건수 표시, 필터 동작 확인 (Task 8 Step 4와 동일 시나리오 최소 2개)
- `데이터 기준:` 시각이 오늘 날짜인지 확인

- [ ] **Step 7: 스케줄 확인 안내**

`gh api repos/dctland-cloud/biz-support-search/actions/workflows` 로 워크플로 활성 상태 확인. 다음날 새벽 5시 자동 실행 여부는 이튿날 `gh run list --limit 3`으로 확인 (후속 확인 항목으로 마이보스에게 보고).

---

## Self-Review 기록

- **스펙 커버리지**: 수집·검증(4-1→Task 6,7), 정규화·판정(4-2→Task 1,2,3,5), 데이터 파일(4-3→Task 7), UI(4-4→Task 8), 자동화·실패 처리(4-5, 5→Task 7,9), 테스트(6→각 태스크 TDD), 보안(7→Global Constraints, Task 9 Step 4). 성공 기준(9)은 Task 8 Step 4·Task 9 Step 6~7에서 검증. 누락 없음.
- **플레이스홀더**: 없음 — 전 태스크 코드/명령/예상 출력 포함.
- **타입 일관성**: `classify_period` 반환 튜플, 레코드 스키마 필드명(`startup_years`, `age_limit`, `eligibility_complete`, `raw_period_text`), `merge_duplicates` 시그니처가 Task 1~8 전체에서 동일함을 확인. app.js가 소비하는 필드명은 공통 스키마 절과 일치.
- 주의: 스펙의 병합 키(제목+기간+기관)는 소스 간 기관 표기 차이로 병합 불가 문제가 있어 제목+기간으로 완화 — 스펙도 동일하게 수정됨(2026-07-16).
