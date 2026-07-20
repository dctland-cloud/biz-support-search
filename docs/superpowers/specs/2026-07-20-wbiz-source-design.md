# wbiz(여성기업종합지원센터) 수집 소스 추가 설계 (2026-07-20)

## 배경
- 여성기업 칩(2026-07-20 배포)의 데이터를 보강하기 위한 세 번째 수집 소스.
- 조사 결과: 공공데이터포털 API 없음. `https://wbiz.or.kr/notice/bizNew.do`가
  서버 렌더링 HTML이라 requests만으로 수집 가능. robots.txt 없음(404).
  상세 URL은 `bizNewDetail.do?nttId=<번호>`, 목록 항목은 `fnViewDetail('<nttId>')` 패턴.

## 결정 사항
1. **수집 대상**: `bizNew.do?searchOp8=recruiting`(모집중) 목록만. pageIndex 순회,
   이미 본 nttId가 반복되거나 빈 페이지면 중단(마지막 페이지 반복 방어). 페이지 사이 1초 대기.
2. **파싱**: 정규식 기반(li 블록 → nttId, 제목 `class="tit"`, 분류 `<i class="green">`,
   신청기간 텍스트). 새 외부 라이브러리 추가하지 않음.
   0건 파싱이면 FetchError(구조 변화 의심) — 기존 검증 철학 유지.
3. **레코드 변환** (`to_record_wbiz`):
   - id `wbiz:<nttId>`, org "여성기업종합지원센터", source "wbiz"
   - **target_types는 항상 ["여성기업"]** → 프론트 여성기업 칩에 공식 태그로 잡힘
   - 지역: 제목에서 표준 지역명 추출(예: "경남센터"→경남, "[울산]"→울산), 없으면 UNKNOWN
   - 분류: 지원사업→창업·사업화, BI입주기업→시설·공간, 교육·행사→교육·컨설팅,
     시설대관→시설·공간, 그 외→기타
   - 기간: `YYYY.MM.DD` 점 표기 파싱(`classify_period_wbiz`), "상시" 계열→ROLLING
   - summary: "신청방법: …" (있을 때만), eligibility_complete: False
4. **병합**: 기존 merge_duplicates(정규화 제목+시작일+마감일) 그대로 사용.
   순서 bizinfo → kstartup → wbiz: 중복 시 기업마당 레코드가 base가 되고
   wbiz의 여성기업 태그가 옮겨 붙음. 제목이 다르면 중복 노출 가능 — 알려진 한계.
5. **실패 처리**: 기존 `_collect` 폴백 구조에 3번째 소스로 추가.
   세 소스 모두 실패 시에만 exit 1. GitHub 러너(해외 IP)에서 차단될 위험 있음 —
   실패해도 직전 데이터 유지, meta.json sources.wbiz로 상태 확인.
6. **프론트 변경 없음**: 여성기업 칩이 target_types 태그를 이미 읽음.

## 검증
- TDD: classify_period_wbiz / 제목 지역 추출 / 목록 파싱(fixture HTML) / to_record_wbiz 테스트 선작성.
- 로컬 실수집으로 programs.json 생성 → 여성기업 칩 결과 증가 확인.
- 배포 후 Actions 로그와 meta.json에서 wbiz 수집 성공 여부 확인(해외 IP 차단 여부).

## 이번 범위 아님
- wbiz 상세 페이지 본문 수집(요약 생성), 제목이 다른 중복의 스마트 병합.
