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
