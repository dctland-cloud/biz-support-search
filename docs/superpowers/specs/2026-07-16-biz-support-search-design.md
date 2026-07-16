# 정부 지원사업 검색 웹앱 — Phase 1 설계

- **작성일**: 2026-07-16
- **상태**: 승인됨 (마이보스, 2026-07-16)
- **선행 문서**: `references/phase0/phase0-report.md` (소스 실측, 2026-07-15)

## 1. 목적

정부 지원사업 공고(기업마당 + K-Startup)를 매일 자동 수집해, **사용자가 웹 화면에서 자기 조건(지역·창업 단계·기업 규모·연령·분야)을 선택하면 신청 가능한 공고만 걸러서 보여주는** 검색 웹앱을 만든다.

- 사용자는 링크로 접속하는 불특정 다수 (특정 기업 프로필을 저장하지 않음)
- 조건 입력은 화면에서 매번 선택 — 개인정보·기업정보를 서버에 저장하지 않음
- 운영 비용 0원, 운영자(마이보스)의 반복 작업 0회를 목표로 함

## 2. 범위

### v1에 포함

- 기업마당 전량(약 1,500건) + K-Startup 모집중(약 260건) 매일 자동 수집
- 조건 필터, 키워드 검색, 정렬, D-day 표시, 자격 판정 3단계 표시
- 정적 웹사이트 링크 공유 (GitHub Pages)

### v1에서 제외 (v2 후보)

- 새 공고 알림 (텔레그램 등)
- 중소벤처24 연동 (API 키 수동 승인 필요 — BLOCKED)
- 즐겨찾기, 로그인, 이용 통계
- 첨부문서(HWP 등) 내용 자동 분석

## 3. 아키텍처

```
[매일 새벽 5시 KST, GitHub Actions 자동 실행]
  기업마당 API ─┐
                ├→ 수집기(Python) → 정규화·판정 → site/data/programs.json
  K-Startup API ┘                                        │
                                                         ▼
                                              GitHub Pages 배포 (정적)
                                                         │
[사용자, 아무 때나]  링크 접속 → 브라우저에서 JSON 로드 → 조건 선택 → 즉시 필터링
```

- **서버 없음.** 수집·판정은 GitHub Actions에서, 검색·필터링은 사용자 브라우저에서 실행
- 기업마당 인증키(`BIZINFO_CRTFC_KEY`)는 **GitHub Actions Secrets**에만 보관 — 저장소·사이트에 절대 노출 금지
- 저장소는 public (GitHub Pages 무료 조건). 공고 데이터는 공공데이터이므로 공개 무방

## 4. 구성요소

### 4-1. 수집기 (`collector/`)

- Python 스크립트. 의존성 최소화 (requests 수준)
- 기업마당: `bizinfoApi.do?dataType=json&searchCnt=0` 전량 1콜
- K-Startup: `getAnnouncementInformation?returnType=json&perPage=1000&cond[rcrt_prgs_yn::EQ]=Y` 모집중 1콜
- 수집 예절: 같은 호스트 호출 간 1초 대기, 명시적 User-Agent
- 검증 (하나라도 실패하면 해당 소스 수집 실패로 처리):
  - 기업마당: HTTP 200이어도 본문에 `reqErr` 있으면 실패. `fetched == totCnt` 확인
  - K-Startup: `currentCount == matchCount` 확인

### 4-2. 정규화·판정 모듈 (`collector/normalize.py`, `collector/judge.py`)

- **지역 정규화**: 17개 시도 표준값 + 비표준 결합값 처리(`전남광주` → 전남, 광주 두 지역으로 분해). 원본 값 보존. 기업마당은 `hashtags`에서 지역 토큰 추출, 지역 없는 공고는 `UNKNOWN`(전국 아님, "지역 무관"으로 표시하지 않음 — 필터에서 항상 노출)
- **기간 상태 판정**: `OPEN`(접수 중) / `ROLLING`(상시·선착순·소진 시까지) / `UPCOMING`(접수 전) / `UNKNOWN`(판정 불가 문구). 기준 시각은 수집 시각(Asia/Seoul). Phase 0에서 확인된 UNKNOWN 문구("차수별 상이", "모집 완료시" 등)는 패턴 사전에 등록해 ROLLING으로 흡수 가능한 것부터 확장
- **중복 병합**: 정규화 제목 + 신청 시작일 + 마감일이 모두 일치하면 동일 공고로 보고 병합 (기관명은 소스 간 표기가 달라 병합 키에서 제외하고 표시용으로만 사용). 병합 시 두 소스 링크 모두 보존. 부분 일치(모호 후보)는 병합하지 않음
- **자격 판정 필드 구조화**:
  - K-Startup: `supt_regin`(지역), `biz_enyy`(업력), `biz_trgt_age`(연령), `aply_trgt`(대상유형) — 4개 모두 구조화 필드라 100% 코드 판정
  - 기업마당: `trgetNm`(대상 카테고리 9종) + `hashtags`(지역)만 판정. 업력·매출 등 세부 요건은 구조화 필드가 없으므로 판정하지 않고 `eligibility_complete=false`로 표시

### 4-3. 데이터 파일 (`site/data/programs.json`)

레코드 공통 스키마 (핵심 필드):

| 필드 | 설명 |
|---|---|
| `id` | 소스 접두어 + 원본 ID (예: `bizinfo:PBLN_xxx`, `kstartup:174xxx`) |
| `title`, `summary` | 공고명, 요약 |
| `source` | `bizinfo` / `kstartup` / `merged` |
| `org` | 소관·주관 기관명 |
| `category` | 지원 분야 (자금, R&D, 수출, 인력, 판로 등 — 소스 분류를 공통 분류로 매핑) |
| `regions` | 정규화 지역 배열 (`["전국"]`, `["전남","광주"]`, `["UNKNOWN"]`) |
| `target_types` | 대상유형 (소상공인, 중소기업, 예비창업자 등) |
| `startup_years` | 업력 조건 (K-Startup만, 없으면 null) |
| `age_limit` | 연령 조건 (K-Startup만, 없으면 null) |
| `period_status` | `OPEN` / `ROLLING` / `UPCOMING` / `UNKNOWN` |
| `apply_start`, `apply_end` | 신청 시작·마감일 (ISO, 없으면 null) |
| `eligibility_complete` | 세부 요건까지 코드 판정 가능 여부 (bool) |
| `url` | 원문 상세페이지 링크 |
| `raw_period_text` | 기간 원문 (판정 근거 표시용) |

메타 파일(`site/data/meta.json`): 수집 시각, 소스별 건수, 소스별 성공/실패 상태.

### 4-4. 웹 UI (`site/`)

- 순수 HTML/CSS/JS 정적 1페이지. 프레임워크·빌드 도구 없음 (관리 단순화)
- 첫 로드 시 `programs.json` 전체 로드(약 1,800건, 수 MB 이내) 후 브라우저 메모리에서 필터링 — 체감 즉시 응답
- **필터**: 지역(17개 시도+전국) / 창업 단계(예비, 3년 미만, 7년 미만, 무관) / 기업 규모·대상(소상공인, 중소기업 등) / 청년(39세 이하) 여부 / 지원 분야
- **결과 카드**: 공고명, 기관명, 분야 태그, 마감 D-day 배지(ROLLING은 "상시" 배지), 자격 표시(✅/⚪), 원문 바로가기 링크
- **자격 표시**: ✅ 신청 가능(선택 조건과 구조화 필드 모두 일치하고 `eligibility_complete=true`) / ⚪ 확인 필요(조건 불일치 없음 + 세부 요건 미판정) / 조건 불일치 공고는 숨김
- **정렬**: 마감 임박순(기본, ROLLING은 뒤로) / 최신순
- **키워드 검색**: 공고명·요약 부분 문자열 일치
- 화면에 데이터 기준 시각(meta.json) 상시 표시. 모바일 대응(반응형)

### 4-5. 자동화 (`.github/workflows/collect.yml`)

- 스케줄: 매일 새벽 5시 KST (`cron: 0 20 * * *` UTC) + 수동 실행 버튼(workflow_dispatch)
- 흐름: 수집 → 검증 → programs.json/meta.json 갱신 커밋 → Pages 배포
- **실패 시**: 한 소스만 실패하면 성공한 소스 + 직전 데이터로 부분 갱신하고 meta에 실패 표시. 전체 실패하면 커밋하지 않음(직전 데이터 유지). 어느 경우든 사이트는 계속 동작

## 5. 오류 처리 원칙

- 수집 실패가 사용자 화면 장애로 이어지지 않게: 사이트는 항상 마지막 성공 데이터를 서빙
- 판정 불확실성은 숨기지 않고 표시: `UNKNOWN`, ⚪ 확인 필요, 데이터 기준 시각
- API 응답 구조 변화 감지: 필수 필드(id, 공고명, 원문 링크) 누락률이 5%를 넘으면 해당 소스 수집 실패로 처리

## 6. 테스트

- 판정 로직(기간 상태, 지역 정규화, 중복 병합, 자격 매칭) 단위 테스트 — pytest
- 테스트 fixture는 `references/phase0/*_sample3.json` 실측 샘플 재사용
- UI는 실제 데이터로 브라우저 확인 (agent-browser 활용)

## 7. 보안·준수 원칙

- 인증키·기업 프로필·수집 이력은 커밋 금지 (`.gitignore` 이중 방어 유지)
- robots.txt 준수: 공식 API만 사용, HTML 크롤링 안 함 (Phase 0 원칙 유지)
- 사용자 입력(선택 조건)은 어디에도 저장·전송하지 않음

## 8. 마이보스가 할 일 (1회성)

1. `gh auth login` — GitHub 계정 연결 (구현 시작 시, 약 2분)
2. 기업마당 인증키를 GitHub Secrets에 등록 (제가 안내하는 화면에서 붙여넣기 1회)

## 9. 성공 기준

- 링크 접속 → 조건 선택 → 3초 이내 결과 표시
- 매일 새벽 자동 갱신이 사람 개입 없이 1주일 이상 연속 성공
- K-Startup 공고의 지역·업력·연령·대상 판정 정확도: 구조화 필드 기준 100% 일치
- 수집 건수가 API 보고 건수와 일치 (fetched == totCnt 검증 통과)
