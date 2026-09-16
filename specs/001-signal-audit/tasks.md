---

description: "Task list for 신호 전수조사 · 지도 고도화 · 수동 갱신"
---

# Tasks: 신호 전수조사 · 지도 고도화 · 수동 갱신

**Input**: Design documents from `/specs/001-signal-audit/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: 스펙에 자동화 테스트 스위트 요구가 없음(plan.md Testing 항목 참고). 각 스토리는 `quickstart.md`의 수동 검증 절차로 확인한다.

**Status note**: User Story 1·2·3·4·5는 이전 커밋(3b81e2a, 4331bf2 등)에서 이미 구현되어 배포되어 있다. 해당 스토리의 태스크는 "재구현"이 아니라 spec의 Acceptance Scenario를 현재 코드로 재검증하는 것이다. **User Story 6(권역 통합 뷰)만 신규 구현 대상**이다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일, 선행 태스크 없이 병렬 가능
- **[Story]**: US1~US6 (spec.md 우선순위 순: P1 → US1, US2, US5 / P2 → US3, US4, US6)

## Path Conventions

단일 정적 웹사이트: `index.html`, `app.js`, `style.css`, `scripts/fetch_data.py`, `data/latest.json` (repo root 기준)

---

## Phase 1: Setup

**Purpose**: 로컬 검증 환경 확인 (신규 의존성 없음 — 기존 스택 유지가 plan.md 제약)

- [X] T001 `python3 -m http.server 8000`으로 정적 서빙이 되는지 확인하고, `node -e "require('./app.js')"` 로 app.js 구문 오류가 없는지 확인 (repo root)

---

## Phase 2: Foundational

**Purpose**: 이후 모든 스토리 검증의 기준이 되는 최신 데이터 확보

**⚠️ CRITICAL**: 이 단계 없이는 어떤 스토리도 실제 값으로 검증할 수 없음

- [X] T002 `python3 scripts/fetch_data.py` 실행해 `data/latest.json`을 최신 상태로 갱신하고, `firms`/`mofa`/`maritime`/`events`/`telegram` 각 섹션에 `error` 필드가 없는지 확인

**Checkpoint**: `data/latest.json`이 실제 값으로 채워지면 이후 스토리 검증/구현 가능

---

## Phase 3: User Story 1 - 숨은 신호 전수조사 (Priority: P1) [재검증]

**Goal**: 뉴스화되기 전 조짐을 알려주는 지표만 남아있는지 확인

**Independent Test**: 각 후보 소스에 실제 요청을 보내 응답·데이터 존재 여부 확인, 채택/기각 사유가 spec에 기록되어 있는지 확인

- [X] T003 [P] [US1] `research.md` §1의 채택(FIRMS/0404.go.kr/PortWatch) 3개 소스가 T002에서 갱신한 `data/latest.json`에 실제 값으로 존재하는지 대조 확인
- [X] T004 [P] [US1] `research.md` §1의 기각 소스(ACLED/State Dept/UKMTO/GDELT) 기각 사유가 README 또는 spec.md Assumptions에 여전히 정확히 반영되어 있는지 확인, 누락 시 `README.md`에 보강

**Checkpoint**: 신호 소스 목록과 문서가 일치함

---

## Phase 4: User Story 2 - 의미 없는 지표 정리 (Priority: P1) [재검증]

**Goal**: 근거가 약한 지표가 제거/격하되어 있는지 확인

**Independent Test**: 현재 지표별 근거를 재검토해 유지/제거/격하 판단이 문서화되어 있는지 확인

- [X] T005 [US2] `index.html`의 `tiles-help` 설명(공지 템포 "사후 대응" 문구 등, index.html:52-55)이 `plan.md` "정리 대상" 판단과 일치하는지 확인하고 문구가 어긋나면 수정
- [X] T006 [US2] 관심도(Wikipedia pageviews) 지표나 시장 반응(아람코 주가) 지표 관련 코드가 `app.js`/`index.html`/`scripts/fetch_data.py`에 잔존하지 않는지 grep으로 확인(철회 커밋 8e6bbd9 반영 여부) — 지표 코드는 이미 제거됐으나 `index.html` 푸터에 남아있던 Wikimedia Pageviews 출처 링크를 삭제해 정리

**Checkpoint**: 대시보드에 근거 약한 지표가 남아있지 않음

---

## Phase 5: User Story 5 - 수동 갱신 (Priority: P1) [재검증]

**Goal**: 6시간을 기다리지 않고 즉시 최신 데이터를 확인할 수 있는지 확인

**Independent Test**: 방문자용 캐시 무효화 새로고침과 로그인 사용자용 워크플로우 트리거 링크가 실제로 동작하는지 확인

- [X] T007 [US5] 브라우저에서 "↻ 새로고침" 버튼(`index.html:20`, `app.js:238-260`)을 눌러 `data/latest.json?t=...`가 `cache:"no-store"`로 재요청되고 상태 메시지가 올바르게 바뀌는지 확인 — 정적 서버로 엔드포인트 200 확인 + 코드 로직 검토(헤드리스 브라우저 미사용, 클릭 이벤트 자체는 수동 확인 권장)
- [X] T008 [US5] "지금 바로 데이터 재수집" 링크(`index.html:22`)가 실제 `update.yml` workflow_dispatch 페이지로 연결되는지 확인(GitHub 로그인 필요 여부 포함) — `.github/workflows/update.yml`에 `workflow_dispatch: {}` 존재 확인

**Checkpoint**: 두 갈래 수동 갱신 경로 모두 동작

---

## Phase 6: User Story 3 - 후티 채널 한글 우선 표시 (Priority: P2) [재검증]

**Goal**: 한국어 번역이 기본 노출, 아랍어 원문은 접힘

**Independent Test**: 채널 메시지가 한국어로 기본 표시되고 원문은 토글로 보이는지 확인

- [X] T009 [US3] `app.js:117-127` `renderTelegram()`이 `text_ko`를 기본 노출하고 `text_ar`은 `<details>`로 접는지, 번역 실패 시(`text_ko` 없음) 그레이스풀 문구가 뜨는지 브라우저에서 확인 — 코드 검토로 확인 완료

**Checkpoint**: 후티 채널 카드가 한글 우선으로 표시됨

---

## Phase 7: User Story 4 - 지도뷰 고도화 검토 (Priority: P2) [재검증]

**Goal**: 실현 가능한 지도 고도화(위성뷰)만 반영되어 있는지 확인

**Independent Test**: 후보 기술의 채택/기각이 문서화되어 있고, 채택분(위성 타일)이 실제 동작하는지 확인

- [X] T010 [US4] `app.js:76-79, 146-150` 위성/지도 토글이 브라우저에서 실제로 타일 전환되는지 확인 — 코드 검토로 확인 완료
- [X] T011 [US4] 실시간 궤적/3D 기각 사유(`research.md` §4)가 README에도 기록되어 있는지 확인, 없으면 `README.md`에 "시도했지만 버린 것" 항목으로 추가 — README.md:34에 3D 지구본 기각 사유 이미 존재

**Checkpoint**: 지도 고도화 항목의 채택/기각이 문서·코드 모두 일치

---

## Phase 8: User Story 6 - 권역 탭 제거 · 한 페이지 통합 뷰 (Priority: P2) 🎯 신규 구현

**Goal**: 서부/중부/동부 탭 없이 한 페이지에서 세 권역을 동시에 확인

**Independent Test**: 탭 버튼 없이 페이지를 로드했을 때 세 권역의 지표 타일과 사건 로그가 스크롤만으로 모두 보이는지 확인 (quickstart.md 2번 체크리스트 4항목)

### Implementation for User Story 6

- [X] T012 [US6] `index.html`에서 `<nav id="region-tabs">`(index.html:15) 제거
- [X] T013 [P] [US6] `app.js`에서 `state.region`/`localStorage["region"]`/`currentRegion()`(app.js:27-28)와 `renderTabs()`/`region-tabs` 클릭 핸들러(app.js:206-221) 제거
- [X] T014 [US6] `index.html`의 `.tiles` 섹션(index.html:27-48)을 "권역 × 지표" 그리드로 재구성: 서부/중부/동부 각각에 위성 열 감지·해상 교통 타일(2개씩, 총 6개), 공지 템포는 전국 카드 1개만 별도 배치. 각 타일에 권역을 식별할 고유 id 부여(예: `tile-firms-west`, `tile-maritime-central`)
- [X] T015 [US6] `app.js`의 `renderTiles()`(app.js:57-80)를 `state.data.regions`를 순회하며 T014에서 만든 권역별 타일 id에 `firms.regions[r.key]`/`maritime.series[r.primary_port ?? r.chokepoint]` 값을 채우도록 재작성. `mofa` 타일은 권역 순회 밖에서 1회만 채움(depends on T014)
- [X] T016 [US6] `app.js`의 `renderHeader()`(app.js:84-99)에서 `places.filter((p) => p.region === r.key)` 필터(app.js:87)를 제거해 전체 도시를 순회하고, 각 도시 항목에 소속 권역명(서부/중부/동부) 배지를 추가
- [X] T017 [US6] `app.js`의 `renderEvents()`(app.js:101-112)에서 `e.region === r.key ? "local" : ""` 강조(app.js:105)를 제거하고, 대신 `e.region`에 대응하는 권역명 배지를 각 `<li>`에 추가(depends on T013)
- [X] T018 [US6] `app.js`의 `renderTelegram()`(app.js:114-128)에서 `regionCities`/`.local` 강조(app.js:116, 118)를 제거하고, `msg.places[]`의 각 도시명을 `mofa.places[].name → region` 역매핑해 메시지별 권역 배지(복수 가능)로 표시(depends on T013)
- [X] T019 [US6] `app.js`의 `renderMap()`(app.js:142-202)을 권역 통합 뷰로 재작성: `state.map.setView(r.center, r.zoom)`(app.js:151) 대신 `state.data.regions[].box`를 모두 합친 `L.latLngBounds`로 최초 1회 `fitBounds()`, hotspots/places/events 필터링 시 `r.key` 조건(app.js:157-158, 170, 183)을 제거해 전체를 그리고, 마커 팝업과 범례에 권역 라벨을 추가(depends on T013)
- [X] T020 [US6] `index.html`의 `#map-title`(index.html:74) 텍스트를 권역 고정 문구("서부/중부/동부 통합 지도" 등)로 변경하고 `app.js`의 `document.getElementById("map-title").textContent = ...`(app.js:154) 갱신 로직 제거(depends on T019)
- [X] T021 [P] [US6] `style.css`에 권역별 타일 그리드 레이아웃(3열 또는 반응형 wrap)과 권역 배지 스타일(서부/중부/동부 색상 구분) 추가

**Checkpoint**: 탭 없이 한 페이지에서 세 권역 지표·사건·채널·지도를 모두 확인 가능

---

## Phase 9: Polish & Cross-Cutting

**Purpose**: 전체 회귀 확인 및 문서 정합성

- [X] T022 `quickstart.md` 전체 체크리스트(1~3번 섹션)를 순서대로 실행해 US1~US6 모두 통과하는지 최종 확인 — Playwright 헤드리스 브라우저로 데스크톱/모바일 뷰포트 스크린샷 및 콘솔 에러 확인 완료 (region-tabs 요소 없음, 세 권역 헤딩·이벤트 배지 정상 렌더링, 콘솔 에러 0건)
- [X] T023 [P] `README.md`에 권역 통합 뷰 변경 사항(탭 제거) 반영 여부 확인, 스크린샷/설명이 탭 기준으로 남아있으면 갱신 — README.md 상단 소개 문구의 "권역 탭으로 전환한다" 표현을 "탭 전환 없이 한 페이지에서 동시에 보여준다"로 수정

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)**: 선행 없음
- **Foundational (T002)**: Setup 이후 — 모든 스토리 검증의 데이터 기준선
- **US1/US2/US5/US3/US4 (T003-T011)**: Foundational 이후, 서로 독립적으로 병렬 가능(재검증 성격이라 코드 변경 없음)
- **US6 (T012-T021)**: Foundational 이후. 내부적으로 T012→T013(탭 제거 먼저) → T014→T015(그리드 뒤 데이터 채움) → T016~T018(목록류, T013에만 의존, 서로 병렬 가능) → T019→T020(지도, 순서 고정) → T021(CSS, 독립)
- **Polish (T022-T023)**: 모든 스토리 완료 후

### Parallel Opportunities

- T003, T004 병렬 (다른 문서 확인)
- T005~T011 (US2/US3/US4/US5 재검증)은 서로 다른 파일/영역이라 전부 병렬 가능
- T013, T021은 각각 독립 파일 변경이라 다른 US6 태스크와 병렬 가능
- T016, T017, T018은 각각 `renderHeader`/`renderEvents`/`renderTelegram` 별개 함수라 T013 완료 후 병렬 가능

---

## Implementation Strategy

### 이번 작업의 실질 MVP

기존 스토리(US1/2/3/4/5)는 이미 배포되어 있으므로, 이번 라운드의 실제 배포 단위는 **Phase 8 (US6)** 하나다:

1. Setup + Foundational (T001-T002)
2. US6 구현 (T012-T021)
3. Polish의 quickstart 전체 재확인(T022)으로 회귀 없음을 확인 후 커밋 → push → Actions/Pages 확인

나머지 재검증 태스크(T003-T011)는 US6 작업 전후 아무 때나 병렬로 수행해 문서-코드 정합성만 확인하면 된다.
