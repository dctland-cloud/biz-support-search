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

## K-Startup 수집 복구 (2026-11)

기존 무인증 `nidapi.k-startup.go.kr` 주소가 HTTP 200 응답으로 웹 방화벽 차단 HTML을 반환하는 경우가 확인되었습니다. 이는 GitHub Actions 장애가 아니라 제공기관 응답이며, JSON으로 해석할 수 없습니다. 차단을 우회하지 않고 공식 인증 API로 전환합니다.

1. [공공데이터포털의 K-Startup 조회서비스](https://www.data.go.kr/data/15125364/openapi.do)에서 활용신청 및 승인을 확인합니다.
2. 저장소 **Settings → Secrets and variables → Actions → New repository secret**에 `KSTARTUP_SERVICE_KEY` 이름으로 **일반 인증키(Decoding)**를 등록합니다. 키를 채팅·코드·커밋에 넣지 마세요.
3. Actions의 `collect-and-deploy`에서 **Run workflow**를 실행합니다.
4. `site/data/meta.json`의 `sources.kstartup.ok`가 `true`인지 확인합니다. 배포 성공만으로 수집 성공을 판단하지 마세요.

키가 설정되면 공식 `apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01`을 사용합니다. 키가 없으면 기존 경로를 유지하되 차단 원인을 명확히 표시합니다. 인증 API 실패 시 무인증 경로로 우회하지 않습니다. 키 등록 전에는 K-Startup 최신 데이터 복구가 완료된 것이 아닙니다.

부분 실패 시 다른 소스의 최신 데이터와 실패 소스의 직전 데이터를 배포한 뒤, 워크플로를 실패 처리하여 실패가 계속 숨겨지지 않도록 합니다.

로컬 실행 시 K-Startup 키는 환경변수 `KSTARTUP_SERVICE_KEY`로 제공합니다. 기업마당과 달리 `~/.biz-support-search/.env`에서는 읽지 않습니다.

로컬 테스트: `python -m pytest -q` (개발 의존성 `pytest` 설치 필요).
