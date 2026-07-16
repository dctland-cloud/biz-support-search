"""원본 공고 → 공통 레코드 변환, 중복 병합, 자격 판정 준비."""
from collector.normalize import (
    classify_period,
    classify_period_kstartup,
    extract_regions_from_hashtags,
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
