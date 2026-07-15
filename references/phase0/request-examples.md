# 실측 요청 예시 (인증키 제거, 2026-07-15 실측)

## 기업마당 지원사업정보 API

```
GET https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do?crtfcKey=****&dataType=json&searchCnt=0
→ HTTP 200, jsonArray 배열 1,527건 (totCnt=1527, fetched==totCnt 일치)
```

- `searchCnt=0` 또는 생략 시 전량 제공 (전량 1콜)
- 무인증 호출 시: HTTP 200 + `{"reqErr":"인증키를 입력해주세요."}` → 200이어도 본문 오류 검사 필수
- 파라미터: crtfcKey(필수), dataType(rss/json), searchCnt, searchLclasId(01금융~09기타), hashtags, pageUnit, pageIndex
- 주요 응답 필드: pblancId, pblancNm, pblancUrl, jrsdInsttNm(소관), excInsttNm(수행), bsnsSumryCn(개요),
  reqstBeginEndDe(신청기간 "YYYY-MM-DD ~ YYYY-MM-DD" 또는 "상시 접수" 등 자유서술),
  trgetNm(지원대상 카테고리), hashtags(지역 포함), reqstMthPapersCn(신청방법), refrncNm(문의처),
  rceptEngnHmpgUrl(신청URL, 55%), fileNm/flpthNm(첨부), totCnt

## K-Startup 지원사업 공고 API (무인증)

```
GET https://nidapi.k-startup.go.kr/api/kisedKstartupService/v1/getAnnouncementInformation?page=1&perPage=1000&returnType=json&cond[rcrt_prgs_yn::EQ]=Y
→ HTTP 200, currentCount=261, matchCount=261 (모집중 전량 1콜)
```

- 필터 없이 호출 시 totalCount=29,430 (마감 이력 전체 포함, 99.1% 비진행) → 반드시 모집중 필터 사용
- returnType 생략 시 XML, `returnType=json` 시 JSON
- perPage=1000 정상 동작 확인 (261건 기준)
- 주요 응답 필드: pbanc_sn(공고번호), biz_pbanc_nm(공고명), pbanc_ctnt(내용), supt_regin(지역),
  biz_enyy(업력), biz_trgt_age(연령), aply_trgt(대상유형), aply_trgt_ctnt(대상 서술),
  aply_excl_trgt_ctnt(제외대상, 48%), pbanc_rcpt_bgng_dt/pbanc_rcpt_end_dt(YYYYMMDD),
  aply_mthd_*(신청방법군), detl_pg_url(상세페이지 100%), sprv_inst(주관), pbanc_ntrp_nm(기관명),
  supt_biz_clsfc(분류), rcrt_prgs_yn(모집진행)

## 공공데이터포털 경유 (참고 — 사용 안 함)

```
GET http://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01?...
→ HTTP 401 Unauthorized (serviceKey 필요) — nidapi 직접 호출로 대체
```
