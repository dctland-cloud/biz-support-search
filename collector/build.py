"""수집 → 정규화 → 병합 → site/data/*.json 생성. 부분 실패 시 직전 데이터 유지."""
import json
import os
import re
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


def _redact(text):
    """오류 문자열에 인증키가 그대로 남지 않도록 마스킹 (meta.json에 커밋됨)."""
    text = re.sub(r"(crtfcKey|serviceKey)=[^&\s\"']+", r"\1=***", text)
    key = load_env_key()
    if key:
        text = text.replace(key, "***")
    return text


def check_missing_rate(records):
    bad = [r for r in records if not all(r.get(f) for f in _REQUIRED)]
    if records and len(bad) / len(records) > 0.05:
        raise FetchError(f"필수 필드 누락 {len(bad)}/{len(records)}건 — 응답 구조 변화 의심")
    return [r for r in records if all(r.get(f) for f in _REQUIRED)]


def _to_records(items, converter, today):
    """원본 항목을 공통 레코드로 변환. 개별 항목 변환 실패는 5%까지 허용(그 이상은 응답 구조 변화로 간주)."""
    good, bad = [], 0
    for item in items:
        try:
            good.append(converter(item, today))
        except Exception:
            bad += 1
    if items and bad / len(items) > 0.05:
        raise FetchError(f"레코드 변환 실패 {bad}/{len(items)}건 — 응답 구조 변화 의심")
    return good


def load_previous(source, data_dir=None):
    data_dir = Path(data_dir) if data_dir else DATA_DIR
    path = data_dir / "programs.json"
    if not path.exists():
        return []
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [r for r in old if r.get("source") in (source, "merged")]


def _collect(name, collect_fn):
    """소스 하나 수집. 실패하면 직전 데이터로 폴백하고 실패 표시."""
    try:
        records = check_missing_rate(collect_fn())
        return records, {"ok": True, "count": len(records), "error": None}
    except Exception as exc:  # 네트워크·검증·파싱 모두 폴백 대상
        records = load_previous(name)
        return records, {"ok": False, "count": len(records), "error": _redact(str(exc))}


def main():
    today = datetime.now(KST).date()

    def collect_bizinfo():
        key = load_env_key()
        if not key:
            raise FetchError("BIZINFO_CRTFC_KEY가 없음 (env 또는 ~/.biz-support-search/.env)")
        return _to_records(fetch.fetch_bizinfo(key), to_record_bizinfo, today)

    def collect_kstartup():
        return _to_records(fetch.fetch_kstartup(), to_record_kstartup, today)

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
