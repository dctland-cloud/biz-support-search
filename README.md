# 정부 지원사업 찾기 (biz-support-search)

기업마당 + K-Startup 공고를 매일 새벽 5시(KST)에 자동 수집해,
조건(지역·업력·연령·대상·분야)을 선택하면 신청 가능한 공고만 보여주는 검색 웹앱.

- 사이트: https://dctland-cloud.github.io/biz-support-search/
- 설계: `docs/superpowers/specs/2026-07-16-biz-support-search-design.md`
- 소스 실측: `references/phase0/phase0-report.md`

## 로컬 실행

```
pip install -r requirements.txt
python -m collector.build      # 수집 (키: ~/.biz-support-search/.env)
python -m http.server 8765 --directory site
```

## 주의

인증키는 커밋 금지 — 로컬 `~/.biz-support-search/.env`, CI는 Actions Secrets.
