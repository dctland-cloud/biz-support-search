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
        if not bgng or not end or len(bgng) != 8 or len(end) != 8:
            raise ValueError
        s = datetime.strptime(bgng, "%Y%m%d").date()
        e = datetime.strptime(end, "%Y%m%d").date()
    except (ValueError, TypeError):
        return ("UNKNOWN", None, None)
    return (_status_from_dates(s, e, today), s.isoformat(), e.isoformat())


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
