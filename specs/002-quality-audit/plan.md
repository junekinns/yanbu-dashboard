# Implementation Plan: 서비스 품질 감사 — 정확성·견고성·명확성

**Branch**: `002-quality-audit` (main 직접 반영) | **Date**: 2026-09-17 | **Spec**: ./spec.md

**Input**: `specs/002-quality-audit/spec.md` — 코드·데이터·문서를 실제로 읽고 실행해 찾은 결함 목록(`research.md`)을 고치는 계획. 새 기능 없음.

## Summary

세 층위의 결함을 고친다. (1) **정확성**: FIRMS "최근 24h"가 실제로는 24~48시간 창이고, 평시가 0/극소일 때 큰 값이 "평시"로 나오며, 외교부 공지 목록이 50건에서 잘려 활발한 시기에 평시가 과소평가되고, 72시간 로그에 5일 전 사건이 남는다. (2) **견고성**: 예상 밖 예외 하나가 스크립트 전체를 죽여 그 시간의 모든 소스가 사라지고, 번역을 매시간 반복해 무료 한도에 기대며, 워크플로우가 push 충돌·무한 대기에 취약하다. (3) **명확성**: "(이전 값)"의 나이, 시간대, 원시 오류 문자열, 탭 제거 후 남은 죽은 문구, 중복 표기, 화면 밖 마커. 전부 기존 파일 4개(`scripts/fetch_data.py`, `app.js`, `index.html`, `.github/workflows/update.yml`)와 README 안에서 끝난다.

## Technical Context

**Language/Version**: Python 3.12 (수집), 바닐라 JS + Leaflet 1.9 + Chart.js 4 (프론트)

**Primary Dependencies**: `requests` 뿐. 추가 없음.

**Storage**: `data/latest.json` 단일 파일. 이전 실행 결과가 `previous`로 읽혀 이력·캐시 역할을 한다.

**Testing**: 자동화 스위트 없음(프로젝트 관행). 검증은 (a) `fetch_data.py` 실행 후 JSON 불변식 검사 스크립트, (b) 소스 URL 고의 파괴 후 재실행, (c) Playwright 헤드리스 스크린샷/텍스트 검사(001에서 확립한 방식), (d) Actions 실행 로그.

**Target Platform**: GitHub Pages(정적) + GitHub Actions(**매시간** cron `7 * * * *`)

**Project Type**: 단일 정적 웹사이트 + 수집 스크립트

**Constraints**: 무료·무키. 오버엔지니어링 금지(사용자 반복 지시). 새 지표·새 화면 금지(이번 스펙의 범위 규칙).

**Scale/Scope**: 개인/가족 사용자. 변경 파일 5개, 추가 LOC 대략 +80 / -30.

## Constitution Check

`.specify/memory/constitution.md`는 아직 템플릿 플레이스홀더 상태라 강제 게이트가 없다. 대신 프로젝트가 스스로 지켜온 원칙을 게이트로 쓴다:

| 원칙 | 이번 계획 | 판정 |
|---|---|---|
| 무료·무키 | 새 외부 의존 없음 | PASS |
| 오버엔지니어링 금지 | 새 파일·새 추상화 없음. 가장 큰 변경이 `main()`의 try/except 래퍼 하나 | PASS |
| "수집 실패만 뜨는 지표는 없느니만 못하다" | stale 나이 표시·짧은 실패 문구로 오히려 강화 | PASS |
| 의미 없는 지표 금지 | 지표 추가 없음. 중부 호르무즈 타일은 제거 대신 정직한 라벨로 | PASS (research.md §C7 판단 근거) |

## Project Structure

### Documentation (this feature)

```text
specs/002-quality-audit/
├── plan.md              # 이 파일
├── research.md          # 감사 결과 + 결정 (Phase 0)
├── data-model.md        # latest.json 필드 변경 (Phase 1)
├── quickstart.md        # 검증 절차 (Phase 1)
└── tasks.md             # /speckit-tasks 가 생성
```

### Source Code (repository root)

```text
scripts/fetch_data.py          # FR-001~010: 창 계산, floor, pageSize, 예외 가드, last_ok_at, 번역 캐시, flights 시간대 평시
app.js                         # FR-004, 011~018: 72h 필터, stale 나이, 실패 문구, 시간대, 경보 한 줄, 지도 bounds, href 이스케이프
index.html                     # FR-005, 014, 017: 도움말·죽은 문구·타일 제목
.github/workflows/update.yml   # FR-009: pull --rebase, timeout-minutes
README.md                      # FR-019
data/latest.json               # 실행 산출물(스키마 변경은 data-model.md)
```

**Structure Decision**: 기존 5개 파일 내부 수정만. 검증 스크립트는 quickstart.md에 인라인 명령으로 두고 저장소에 파일을 추가하지 않는다(프로젝트에 테스트 디렉터리를 새로 만드는 것 자체가 범위 밖).

## 변경 설계 (research.md 결정을 코드 위치로 매핑)

### 정확성 (US1)

- **FR-001 롤링 24h** — `fetch_firms`: 각 hotspot에 `acq_date`+`acq_time`으로 UTC datetime을 붙이고, `last24h`/`flares24h`를 `ts >= now-24h`로 센다. `daily_counts`·`history`·`baseline`은 그대로(일별 중앙값). 도움말에 "위성 패스 직후 출렁일 수 있음" 한 줄.
- **FR-002 평시 하한** — `ratio(value, baseline)` 호출부에서 `max(baseline, floor)`: FIRMS floor 2(3건부터 주의, 6건부터 위험), 공지 템포 floor 1. `tier_up` 자체는 안 건드린다. 하한은 표시 평시값이 아니라 비율 계산에만 적용한다(사용자에게는 실제 중앙값을 보여준다).
- **FR-003 공지 목록** — `MOFA_NOTICE_URL`의 `pageSize=50` → `100`(실측 200 OK, 99건 반환).
- **FR-004 72h 필터** — `renderEvents`에서 `new Date(e.iso) >= now-72h`로 거른다. `renderMap`은 이미 `since`로 거르고 있음.
- **FR-005 flights** — `history` 키는 그대로 `YYYY-MM-DDTHH`; 평시는 같은 `HH`의 과거 값 중앙값(≥3개). `maxage` 14400 → 900. cap 120 → 336(14일×24). `index.html` 도움말 "약 이틀" → "같은 시각 기록이 3일치 쌓일 때까지".

### 견고성 (US2)

- **FR-006 예외 가드** — `main()`에 `def safe(fetch, *a)`: `try: return fetch(*a) except Exception as exc: return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "fetched_at": now_iso()}`. 각 소스 호출을 `carry_over(safe(...), previous[...])`로. 기존 함수 내부의 세밀한 except는 유지(원인 메시지가 더 구체적).
- **FR-007 last_ok_at** — 각 fetch 성공 시 `result["last_ok_at"] = result["fetched_at"]`. `carry_over`가 `kept`에 `last_ok_at`을 포함하도록 제외 목록에서 빼지 않는다(현재 제외 목록은 ok/error/fetched_at 뿐이므로 자동 보존).
- **FR-008 번역 캐시** — `fetch_telegram(previous)`: `cache = {(m["url"], hash(m["text_ar"])): m["text_ko"] for m in previous.get("messages", [])}`. 히트면 API 호출 생략. 원문 해시로 편집된 메시지는 재번역.
- **FR-009 워크플로우** — `git pull --rebase -X theirs origin main` 을 commit 뒤 push 앞에, `timeout-minutes: 15` 를 job에.
- **FR-010** — `fetch_flights`의 `requests.get` → `get(url_with_params, BROWSER_HEADERS, timeout=20)`.

### 명확성 (US3)

- **FR-011 stale 나이** — `staleTag(src)`: `last_ok_at`이 있으면 경과를 "N시간 전 값"/"N일 전 값"으로, 없으면 기존 "(이전 값)".
- **FR-012 실패 문구** — `fillTile`에 `title` 파라미터 추가. 실패 분기의 `sub`는 "수집 실패 — 다음 갱신 때 재시도", `title`에 원시 오류.
- **FR-013 시간대** — `last-updated`를 `toLocaleString("ko-KR", { timeZone: "Asia/Riyadh", ... })` + " (사우디 현지)". 사건·채널·화점이 이미 현지/UTC로 명시되어 있어 페이지 전체가 일관된다.
- **FR-014 죽은 문구** — `index.html` 사건 로그 각주의 "붉은 줄 = 선택한 권역" 삭제, 도움말 summary "이 세 지표는" → "이 지표들은".
- **FR-015 경보 한 줄** — `renderHeader`: 3단계 이상 지명만 권역 배지와 함께 나열, 그 외의 기본 단계는 전국 최빈값 하나로 "그 외 전 지역 특별여행주의보".
- **FR-016 지도 bounds** — `combinedBounds`가 `regions[].box` ∪ `mofa.places[].(lat,lon)`.
- **FR-017 중부 타일 제목** — `renderRegionTiles`에서 `r.primary_port`가 없으면 제목을 "해상 교통 · 호르무즈(전국)"로.
- **FR-018 href 이스케이프** — `href="${esc(url)}"` 4곳.

### 문서 (US4)

- **FR-019** — README: "선택 권역" 2곳, "권역 지도: 선택 권역만", 표 제목 "세 가지 지표"→"지표", "시도했지만 버린 것"의 FlightRadar24 줄을 "실험 중" 섹션으로 이동.

## 작업 순서

1. `fetch_data.py` 정확성 3건(FR-001/002/003) → 로컬 실행 → JSON 불변식 검사
2. `fetch_data.py` 견고성(FR-006/007/008/010) → URL 고의 파괴 실행으로 검증
3. `app.js`/`index.html` 명확성(FR-004/011~018) → Playwright 텍스트·스크린샷 검사
4. 워크플로우(FR-009) + README(FR-019)
5. 커밋 → push → Actions 1회 성공 확인 → Pages 확인

## Complexity Tracking

위반 없음.
