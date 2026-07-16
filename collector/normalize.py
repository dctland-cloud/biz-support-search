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
