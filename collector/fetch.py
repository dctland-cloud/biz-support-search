"""공식 API 호출 + 응답 검증. HTTP 200이어도 본문 오류를 반드시 검사한다."""
import time

import requests

USER_AGENT = "biz-support-search/1.0 (+https://github.com/dctland-cloud/biz-support-search)"
BIZINFO_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
KSTARTUP_URL = "https://nidapi.k-startup.go.kr/api/kisedKstartupService/v1/getAnnouncementInformation"
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
