"""공식 API 호출 + 응답 검증. HTTP 200이어도 본문 오류를 반드시 검사한다."""
import re
import time

import requests

USER_AGENT = "biz-support-search/1.0 (+https://github.com/dctland-cloud/biz-support-search)"
BIZINFO_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
KSTARTUP_URL = "https://nidapi.k-startup.go.kr/api/kisedKstartupService/v1/getAnnouncementInformation"
WBIZ_URL = "https://wbiz.or.kr/notice/bizNew.do"
_HEADERS = {"User-Agent": USER_AGENT}
_TIMEOUT = (15, 120)
_MAX_PAGES = 50
_RETRIES = 3
_BACKOFF_SECONDS = (30, 60)


class FetchError(Exception):
    pass


def _get_with_retry(session, url, params):
    for attempt in range(_RETRIES):
        try:
            resp = session.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            if attempt == _RETRIES - 1:
                raise
            time.sleep(_BACKOFF_SECONDS[attempt])


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
    if tot is None:
        raise FetchError("bizinfo: totCnt 필드 없음 — 응답 구조 변화 의심")
    if int(tot) != len(items):
        raise FetchError(f"bizinfo: totCnt {tot} != fetched {len(items)}")
    return items


def fetch_bizinfo(crtfc_key, session=None):
    s = session or requests.Session()
    resp = _get_with_retry(
        s,
        BIZINFO_URL,
        params={"crtfcKey": crtfc_key, "dataType": "json", "searchCnt": 0},
    )
    return validate_bizinfo(resp.json())


def validate_kstartup_page(payload):
    for key in ("currentCount", "matchCount", "data"):
        if key not in payload:
            raise FetchError(f"kstartup: 응답에 {key} 없음")
    return payload


# wbiz 사업공고 목록은 API가 없어 서버 렌더링 HTML을 파싱한다 (2026-07 실측 구조)
_WBIZ_LI_SPLIT = re.compile(r"<li\b[^>]*>")
_WBIZ_ID = re.compile(r"fnViewDetail\('(\d+)'\)")
_WBIZ_TITLE = re.compile(r'class="tit">(.*?)</span>', re.S)
# 분류 라벨의 class는 카테고리마다 다름(green/blue/blue2 …) — 상태 라벨(ing 등)만 제외
_WBIZ_CATEGORY = re.compile(r'<i class="([^"]+)">\s*(.*?)\s*</i>', re.S)
_WBIZ_STATUS_LABELS = ("모집중", "모집마감")
_WBIZ_DL = re.compile(r'<dl class="(i1|i2)">.*?<dd>(.*?)</dd>', re.S)
_WBIZ_TAG = re.compile(r"<[^>]+>")


def _wbiz_text(fragment):
    return re.sub(r"\s+", " ", _WBIZ_TAG.sub(" ", fragment or "")).strip()


def parse_wbiz_list(html):
    """목록 HTML → [{nttId, title, category, period_text, method}]. 항목이 없으면 []."""
    items = []
    for chunk in _WBIZ_LI_SPLIT.split(html)[1:]:
        found_id = _WBIZ_ID.search(chunk)
        found_title = _WBIZ_TITLE.search(chunk)
        if not (found_id and found_title):
            continue
        category = next(
            (_wbiz_text(text) for cls, text in _WBIZ_CATEGORY.findall(chunk)
             if cls != "ing" and _wbiz_text(text) not in _WBIZ_STATUS_LABELS),
            "",
        )
        dls = {key: _wbiz_text(body) for key, body in _WBIZ_DL.findall(chunk)}
        items.append({
            "nttId": found_id.group(1),
            "title": _wbiz_text(found_title.group(1)),
            "category": category,
            "period_text": dls.get("i1", ""),
            "method": dls.get("i2", ""),
        })
    return items


def fetch_wbiz(session=None):
    """모집중 공고를 페이지 순회로 수집. 새 항목이 없는 페이지가 나오면 중단."""
    s = session or requests.Session()
    items, seen, page = [], set(), 1
    while True:
        if page > _MAX_PAGES:
            raise FetchError(f"wbiz: 페이지 상한 {_MAX_PAGES} 초과")
        resp = _get_with_retry(
            s, WBIZ_URL, params={"searchOp8": "recruiting", "pageIndex": page}
        )
        new = [it for it in parse_wbiz_list(resp.text) if it["nttId"] not in seen]
        if not new:
            break
        seen.update(it["nttId"] for it in new)
        items.extend(new)
        page += 1
        time.sleep(1)  # 같은 호스트 예절: 페이지 사이 1초 대기
    if not items:
        raise FetchError("wbiz: 공고 목록 파싱 0건 — 페이지 구조 변화 의심")
    return items


def fetch_kstartup(session=None):
    s = session or requests.Session()
    items, page = [], 1
    while True:
        if page > _MAX_PAGES:
            raise FetchError(f"kstartup: 페이지 상한 {_MAX_PAGES} 초과")
        resp = _get_with_retry(
            s,
            KSTARTUP_URL,
            params={
                "page": page,
                "perPage": 1000,
                "returnType": "json",
                "cond[rcrt_prgs_yn::EQ]": "Y",
            },
        )
        payload = validate_kstartup_page(resp.json())
        items.extend(payload["data"])
        if len(items) >= payload["matchCount"] or not payload["data"]:
            break
        page += 1
        time.sleep(1)  # 같은 호스트 예절: 페이지 사이 1초 대기
    if len(items) != payload["matchCount"]:
        raise FetchError(f"kstartup: matchCount {payload['matchCount']} != fetched {len(items)}")
    return items
