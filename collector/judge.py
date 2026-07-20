"""원본 공고 → 공통 레코드 변환, 중복 병합, 자격 판정 준비."""
import re

from collector.normalize import (
    classify_period,
    classify_period_kstartup,
    classify_period_wbiz,
    extract_regions_from_hashtags,
    extract_regions_from_title,
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


def to_record_wbiz(item, today):
    status, start, end = classify_period_wbiz(item.get("period_text"), today)
    title = (item.get("title") or "").strip()
    method = (item.get("method") or "").strip()
    ntt_id = item.get("nttId", "")
    return {
        "id": f"wbiz:{ntt_id}",
        "title": title,
        "summary": f"신청방법: {method}" if method and method != "-" else None,
        "source": "wbiz",
        "org": "여성기업종합지원센터",
        "category": map_category("wbiz", item.get("category")),
        "raw_category": item.get("category"),
        "regions": extract_regions_from_title(title),
        "target_types": ["여성기업"],  # wbiz 공고는 전부 여성기업 대상
        "startup_years": None,
        "age_limit": None,
        "period_status": status,
        "apply_start": start,
        "apply_end": end,
        "listed_at": start,
        "eligibility_complete": False,
        "url": f"https://wbiz.or.kr/notice/bizNewDetail.do?nttId={ntt_id}",
        "alt_url": None,
        "raw_period_text": (item.get("period_text") or "").strip(),
    }


_TITLE_NOISE = re.compile(r"[\s\[\]()〔〕『』「」《》〈〉<>·ㆍ,.\-~“”‘’\"']+")


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
