import pytest
import requests

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


def test_bizinfo_totcnt_absent_fails():
    with pytest.raises(FetchError, match="totCnt"):
        validate_bizinfo({"jsonArray": [{"pblancId": "A"}]})


class _FakeResp:
    def raise_for_status(self):
        pass

    def json(self):
        return {"currentCount": 1, "matchCount": 10**9, "data": [{"pbanc_sn": 1}]}


class _FakeSession:
    def get(self, *a, **kw):
        return _FakeResp()


def test_kstartup_page_cap(monkeypatch):
    import collector.fetch as fetch_mod

    monkeypatch.setattr(fetch_mod.time, "sleep", lambda s: None)
    with pytest.raises(FetchError, match="페이지 상한"):
        fetch_mod.fetch_kstartup(session=_FakeSession())


class _FakeSingleRespKstartup:
    def raise_for_status(self):
        pass

    def json(self):
        return {"currentCount": 1, "matchCount": 1, "data": [{"pbanc_sn": 1}]}


class _FlakySession:
    """처음 두 번은 ConnectionError, 세 번째부터는 정상 응답."""

    def __init__(self, fail_times):
        self.fail_times = fail_times
        self.calls = 0

    def get(self, *a, **kw):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise requests.ConnectionError("연결 실패")
        return _FakeSingleRespKstartup()


class _AlwaysFailSession:
    def __init__(self):
        self.calls = 0

    def get(self, *a, **kw):
        self.calls += 1
        raise requests.ConnectionError("연결 실패")


def test_fetch_kstartup_retries_then_succeeds(monkeypatch):
    import collector.fetch as fetch_mod

    monkeypatch.setattr(fetch_mod.time, "sleep", lambda s: None)
    session = _FlakySession(fail_times=2)
    items = fetch_mod.fetch_kstartup(session=session)
    assert items == [{"pbanc_sn": 1}]


def test_fetch_kstartup_raises_after_max_retries(monkeypatch):
    import collector.fetch as fetch_mod

    monkeypatch.setattr(fetch_mod.time, "sleep", lambda s: None)
    session = _AlwaysFailSession()
    with pytest.raises(requests.RequestException):
        fetch_mod.fetch_kstartup(session=session)
    assert session.calls == 3


from collector.fetch import parse_wbiz_list


def _wbiz_li(ntt_id, title, category="BI입주기업", cat_class="green", period="2026.07.20 (월) 00:00 ~ <br/>2026.08.12 (수) 18:00까지", method="이메일 접수(wslee@wbiz.or.kr)"):
    return f'''
    <li>
        <a href="javascript:void(0);" onclick="fnViewDetail('{ntt_id}');">
            <span class="type">
                <i class="ing">모집중</i>
                <i class="{cat_class}">{category}</i>
            </span>
            <span class="tit">{title}</span>
            <span class="dls">
                <dl class="i1"><dt>신청기간</dt><dd> {period} </dd></dl>
                <dl class="i2"><dt>신청방법</dt><dd> {method} </dd></dl>
            </span>
            <span class="btn btn_gwg" onclick="fnButtonAction('{ntt_id}', '모집중', 'N');">내용보기</span>
        </a>
    </li>'''


def test_parse_wbiz_list_extracts_fields():
    html = "<ul>" + _wbiz_li("1018", "(재)여성기업종합지원센터 경남센터 제2차 입주기업 모집 공고(∼8.12까지)") + "</ul>"
    items = parse_wbiz_list(html)
    assert len(items) == 1
    it = items[0]
    assert it["nttId"] == "1018"
    assert it["title"] == "(재)여성기업종합지원센터 경남센터 제2차 입주기업 모집 공고(∼8.12까지)"
    assert it["category"] == "BI입주기업"
    assert "2026.07.20" in it["period_text"] and "2026.08.12" in it["period_text"]
    assert it["method"] == "이메일 접수(wslee@wbiz.or.kr)"


def test_parse_wbiz_list_empty_returns_no_items():
    assert parse_wbiz_list("<html><body><ul></ul></body></html>") == []


def test_parse_wbiz_list_category_class_varies():
    # 실측: 분류마다 class가 다름 — green(BI입주기업), blue(지원사업), blue2(교육·행사)
    html = ("<ul>"
            + _wbiz_li("7", "지원사업 공고", category="지원사업", cat_class="blue")
            + _wbiz_li("8", "교육 공고", category="교육·행사", cat_class="blue2")
            + "</ul>")
    items = parse_wbiz_list(html)
    assert items[0]["category"] == "지원사업"
    assert items[1]["category"] == "교육·행사"


class _WbizPageSession:
    """페이지별 HTML을 돌려주는 가짜 세션. 범위를 넘으면 마지막 페이지를 반복(실제 게시판 행태)."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = 0

    def get(self, url, params=None, **kw):
        self.calls += 1
        idx = min(params["pageIndex"], len(self.pages)) - 1

        class R:
            text = self.pages[idx]

            def raise_for_status(self):
                pass

        return R()


def test_fetch_wbiz_paginates_and_stops_on_repeat(monkeypatch):
    import collector.fetch as fetch_mod

    monkeypatch.setattr(fetch_mod.time, "sleep", lambda s: None)
    page1 = "<ul>" + _wbiz_li("1", "공고 하나") + _wbiz_li("2", "공고 둘") + "</ul>"
    page2 = "<ul>" + _wbiz_li("3", "공고 셋") + "</ul>"
    session = _WbizPageSession([page1, page2])
    items = fetch_mod.fetch_wbiz(session=session)
    assert [it["nttId"] for it in items] == ["1", "2", "3"]
    assert session.calls == 3  # 3페이지째(2페이지 반복)에서 새 항목 없음 → 중단


def test_fetch_wbiz_empty_board_raises(monkeypatch):
    import collector.fetch as fetch_mod

    monkeypatch.setattr(fetch_mod.time, "sleep", lambda s: None)
    session = _WbizPageSession(["<ul></ul>"])
    with pytest.raises(FetchError, match="wbiz"):
        fetch_mod.fetch_wbiz(session=session)
