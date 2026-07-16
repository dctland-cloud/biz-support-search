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
