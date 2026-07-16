import json
from datetime import date, timedelta

import pytest

from collector import build as build_mod
from collector.build import _redact, _to_records, check_missing_rate, load_previous
from collector.fetch import FetchError


def _rec(i, source="bizinfo", **kw):
    base = {
        "id": f"{source}:{i}",
        "title": f"공고{i}",
        "url": "https://x",
        "source": source,
        "period_status": "OPEN",
        "apply_start": None,
        "apply_end": None,
    }
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


def test_load_previous_corrupt_file_returns_empty(tmp_path):
    (tmp_path / "programs.json").write_text("{not valid json", encoding="utf-8")
    assert load_previous("bizinfo", tmp_path) == []


def test_to_records_tolerates_up_to_5pct_malformed():
    def converter(item, today):
        if item == "bad":
            raise ValueError("malformed")
        return {"ok": item}

    items = ["good"] * 29 + ["bad"]  # 1/30 ≈ 3.3% — 허용 범위
    result = _to_records(items, converter, None)
    assert len(result) == 29


def test_to_records_fails_over_5pct_malformed():
    def converter(item, today):
        if item == "bad":
            raise ValueError("malformed")
        return {"ok": item}

    items = ["good"] * 18 + ["bad"] * 2  # 2/20 = 10% — 허용 초과
    with pytest.raises(FetchError):
        _to_records(items, converter, None)


def test_redact_masks_crtfckey_and_real_key(monkeypatch):
    monkeypatch.setattr(build_mod, "load_env_key", lambda: "SECRET123")
    text = "요청 실패: https://api.example/?crtfcKey=SECRET123&other=1"
    redacted = _redact(text)
    assert "SECRET123" not in redacted
    assert "crtfcKey=***" in redacted


def _kstartup_item(pbanc_sn=999, days_span=10):
    today = date.today()
    return {
        "pbanc_sn": pbanc_sn,
        "biz_pbanc_nm": "테스트 공고",
        "pbanc_ctnt": "테스트 내용",
        "pbanc_ntrp_nm": "테스트기관",
        "supt_regin": "전국",
        "aply_trgt": "중소기업",
        "pbanc_rcpt_bgng_dt": (today - timedelta(days=1)).strftime("%Y%m%d"),
        "pbanc_rcpt_end_dt": (today + timedelta(days=days_span)).strftime("%Y%m%d"),
        "detl_pg_url": f"https://k-startup.example/{pbanc_sn}",
    }


def test_main_partial_failure_uses_previous(tmp_path, monkeypatch):
    monkeypatch.setattr(build_mod, "DATA_DIR", tmp_path)
    prev = [_rec(1, "bizinfo")]
    (tmp_path / "programs.json").write_text(json.dumps(prev), encoding="utf-8")
    monkeypatch.setattr(build_mod, "load_env_key", lambda: "fake-key")

    def fake_fetch_bizinfo(key, session=None):
        raise FetchError("bizinfo 인증 실패")

    def fake_fetch_kstartup(session=None):
        return [_kstartup_item()]

    monkeypatch.setattr(build_mod.fetch, "fetch_bizinfo", fake_fetch_bizinfo)
    monkeypatch.setattr(build_mod.fetch, "fetch_kstartup", fake_fetch_kstartup)

    build_mod.main()

    programs = json.loads((tmp_path / "programs.json").read_text(encoding="utf-8"))
    ids = {r["id"] for r in programs}
    assert "bizinfo:1" in ids
    assert "kstartup:999" in ids

    meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert meta["sources"]["bizinfo"]["ok"] is False
    assert meta["sources"]["kstartup"]["ok"] is True


def test_main_both_fail_exits_without_write(tmp_path, monkeypatch):
    monkeypatch.setattr(build_mod, "DATA_DIR", tmp_path)
    monkeypatch.setattr(build_mod, "load_env_key", lambda: None)

    def fake_fetch_kstartup(session=None):
        raise FetchError("kstartup 오류")

    monkeypatch.setattr(build_mod.fetch, "fetch_kstartup", fake_fetch_kstartup)

    with pytest.raises(SystemExit) as exc_info:
        build_mod.main()

    assert exc_info.value.code == 1
    assert not (tmp_path / "programs.json").exists()
    assert not (tmp_path / "meta.json").exists()
