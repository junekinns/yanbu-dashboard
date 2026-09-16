---

description: "Task list for 서비스 품질 감사 — 정확성·견고성·명확성"
---

# Tasks: 서비스 품질 감사 — 정확성·견고성·명확성

**Input**: Design documents from `/specs/002-quality-audit/`
**Prerequisites**: plan.md, spec.md, research.md(결함 근거), data-model.md, quickstart.md(검증 명령)

**Tests**: 자동화 스위트 없음(프로젝트 관행). 각 스토리 끝에 quickstart.md의 해당 섹션을 실행하는 검증 태스크를 둔다.

**Scope rule**: 새 지표·새 화면·새 파일 없음. 변경 파일은 `scripts/fetch_data.py`, `app.js`, `index.html`, `.github/workflows/update.yml`, `README.md` 다섯 개뿐이다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일, 선행 태스크 없이 병렬 가능. 같은 파일을 만지는 태스크끼리는 [P]를 붙이지 않는다.
- **[Story]**: US1 정확성(P1) / US2 견고성(P1) / US3 명확성(P2) / US4 문서(P3)

## Path Conventions

단일 정적 웹사이트, repo root 기준. 줄 번호는 커밋 `cfb5fd9` 시점.

---

## Phase 1: Setup

- [X] T001 로컬 실행 환경 확인: `requests`가 있는 파이썬(001의 스크래치 venv 재사용 가능)으로 `python3 scripts/fetch_data.py` 1회 실행해 `data/latest.json`에 `previous`로 쓸 최신 값을 만들고, `node --check app.js` 통과 확인

---

## Phase 2: Foundational

**Purpose**: US2(견고성)와 US3(stale 나이 표시)이 공통으로 기대는 `last_ok_at` + 포괄 예외 가드. 한 곳에서 끝난다.

- [X] T002 `scripts/fetch_data.py` `main()`(551-568)에 `safe(fetch, *args)` 래퍼 추가: `try: r = fetch(*args) except Exception as exc: r = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "fetched_at": now_iso()}`; `r["ok"]`이면 `r["last_ok_at"] = r["fetched_at"]`. 7개 소스 호출(556-562)을 모두 `carry_over(safe(...), previous.get(k, {}))`로 바꾼다. `carry_over`(176-180)는 제외 목록에 `last_ok_at`이 없으므로 stale 시 자동 보존됨 — 변경 불필요. (FR-006, FR-007)

**Checkpoint**: 실행 후 모든 `ok: true` 소스에 `last_ok_at == fetched_at`

---

## Phase 3: User Story 1 - 지표가 거짓말하지 않는다 (Priority: P1) 🎯 MVP

**Goal**: 배지 계산의 체계적 편향·경계 오류·라벨 불일치 제거

**Independent Test**: quickstart.md §1 불변식 스크립트가 `OK`

- [X] T003 [US1] `scripts/fetch_data.py` `fetch_firms`(185-231): hotspot dict(197-198)에 `acq_date`+`acq_time`(UTC, `HHMM`)으로 만든 타임스탬프를 붙이고, `last24h`(219)·`flares24h`(214)를 `yesterday` 비교 대신 `ts >= now-24h`로 센다. `daily_counts`/`history`/`baseline`(211-220)은 그대로. `hotspots` 출력 필드에는 타임스탬프를 추가하지 않는다(프론트가 이미 date+time으로 계산). (FR-001)
- [X] T004 [US1] `scripts/fetch_data.py` 비율 하한: 226행 `tier_up(ratio(last24h, max(baseline or 0, 2)))`, 310-311행 `ratio(counts[-1], max(baseline, 1))`. 출력 `baseline` 필드는 실제 중앙값 유지. (FR-002)
- [X] T005 [US1] `scripts/fetch_data.py:89` `MOFA_NOTICE_URL`의 `pageSize=50` → `pageSize=100`. (FR-003)
- [X] T006 [US1] flights 평시 재정의: `scripts/fetch_data.py:529-538` — `now_key[-2:]`(UTC 시각)와 같은 시각을 가진 과거 history 값의 중앙값을 `baseline`으로(3개 미만이면 `None`), 표본 수를 `baseline_n`으로 출력, cap `[-120:]` → `[-336:]`; 97-98행 `maxage` 14400 → 900. `index.html` 도움말(48행 "홍해 상공 회피" 항목)의 "기준선이 쌓이기 전(약 이틀)"을 "같은 시각 기록이 3일치 쌓일 때까지"로. `app.js:74` sub 문구에 `baseline_n`이 있으면 "(수집 중 n/3)" 표시. (FR-005)
- [X] T007 [US1] `app.js` `renderEvents`(148-160): `events`를 `new Date(e.iso) >= Date.now() - 72*3600e3`로 거른 뒤 렌더. 빈 목록 문구는 그대로. (FR-004)
- [X] T008 [US1] `python3 scripts/fetch_data.py` 실행 후 quickstart.md §1 불변식 스크립트 실행 → `OK`. 실패하면 T003~T006으로 돌아간다.

**Checkpoint**: 라벨·배지·평시가 데이터와 일치

---

## Phase 4: User Story 2 - 한 소스가 죽어도 대시보드가 죽지 않는다 (Priority: P1)

**Goal**: 어떤 예외·충돌·한도에도 그 시간의 갱신이 통째로 사라지지 않음

**Independent Test**: quickstart.md §2a~2d

- [X] T009 [US2] `scripts/fetch_data.py` 번역 캐시: `fetch_telegram()` → `fetch_telegram(previous)`, `main()`의 호출(560)에 `previous.get("telegram", {})` 전달. 함수 안에서 `cache = {(m["url"], hashlib.sha1(m["text_ar"].encode()).hexdigest()): m["text_ko"] for m in previous.get("messages", []) if m.get("text_ko")}`를 만들고, 461-463행 루프에서 키가 있으면 `translate_ar_ko` 호출 없이 재사용. `import hashlib` 추가. (FR-008)
- [X] T010 [US2] `scripts/fetch_data.py:521` `requests.get(FLIGHTS_URL, params=..., headers=BROWSER_HEADERS, timeout=20)` → `get(FLIGHTS_URL + "?" + urlencode(FLIGHTS_PARAMS), BROWSER_HEADERS, timeout=20)` (`urllib.parse.urlencode` import). 재시도 3회 헬퍼로 통일. (FR-010)
- [X] T011 [P] [US2] `.github/workflows/update.yml`: `jobs.update`에 `timeout-minutes: 15`; "Commit if changed" 스텝의 commit 뒤·push 앞에 `git pull --rebase -X theirs origin main` 추가(커밋이 없었을 때도 무해). (FR-009)
- [X] T012 [US2] quickstart.md §2a(URL 고의 파괴 → exit 0, 해당 소스만 stale+last_ok_at), §2b(AttributeError 주입 → events만 stale), §2c(두 번째 실행 번역 호출 0), §2d(grep) 실행. 각 실험 뒤 정상 실행으로 `latest.json` 원복.

**Checkpoint**: 소스 하나를 어떻게 죽여도 나머지는 살아서 저장됨

---

## Phase 5: User Story 3 - 교민 가족이 오해 없이 읽는다 (Priority: P2)

**Goal**: 나이·시간대·오류·죽은 문구·중복·화면 밖 마커 정리

**Independent Test**: quickstart.md §3 Playwright 검사(죽은 문구 0, 시간대 라벨 있음, 사건 72h 이내, "그 외 전 지역" 1회, pageerror 0)

- [X] T013 [US3] `app.js:23` `staleTag(src)`: `src.stale`이고 `src.last_ok_at`이 있으면 경과 시간을 계산해 48시간 미만은 " (N시간 전 값)", 이상은 " (N일 전 값)"; `last_ok_at` 없으면 기존 " (이전 값)". (FR-011)
- [X] T014 [US3] `app.js` `fillTile`(49-58)에 `title` 옵션 추가해 `tile.title = title || ""`; 실패 분기 4곳(66, 76, 107, 115)의 `sub`를 `"수집 실패 — 다음 갱신 때 재시도"`로, 원시 오류는 `title`로. (FR-012)
- [X] T015 [US3] `app.js` `last-updated` 2곳(299-300, 317-318): `toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Riyadh" })` + `" (사우디 현지)"`. 중복이므로 `setLastUpdated(iso)` 헬퍼 하나로 합친다. (FR-013)
- [X] T016 [P] [US3] `index.html`: 45행 "이 세 지표는 어떻게 계산되나요?" → "이 지표들은 어떻게 계산되나요?"; 59행 각주에서 " 붉은 줄 = 선택한 권역." 삭제. (FR-014)
- [X] T017 [US3] `app.js` `renderHeader`(131-140) + `regionGroupSummary`(121-129): 권역별로는 `level >= 3` 지명만(권역 배지 + 지명 + 단계), 권역에 3단계가 없으면 그 권역 항목 생략; 마지막에 `level < 3`인 전체 도시의 최빈 단계 하나를 "그 외 전 지역 <strong>{단계}</strong>"로 한 번만 붙인다. (FR-015)
- [X] T018 [US3] `app.js` `combinedBounds`(195-199)를 `combinedBounds(regions, places)`로: region box 꼭짓점 + `places`의 `(lat, lon)`을 모두 `L.latLngBounds`에 `extend`. 209행 호출에 `d.mofa?.places || []` 전달. (FR-016)
- [X] T019 [US3] `app.js` `renderRegionTiles`(93): `r.primary_port`가 없으면 `<h3>해상 교통 · 호르무즈(전국 수출 회랑)</h3>`, 있으면 기존 "해상 교통". (FR-017)
- [X] T020 [US3] `app.js` `href="${n.url}"`(144), `href="${e.url}"`(157), `href="${msg.url}"`(173), `href="${n.url}"`(188)와 지도 팝업의 `href="${e.url}"`(252)를 `esc(...)`로. (FR-018)
- [X] T021 [US3] `node --check app.js` → 정적 서버 → quickstart.md §3 Playwright 스크립트 실행. 추가로 §2a 파괴 실행 직후 페이지를 열어 "(N시간 전 값)"과 실패 타일의 한국어 문구를 스크린샷으로 확인 후 정상 실행으로 원복.

**Checkpoint**: 문구·시간대·나이·마커 모두 검사 통과

---

## Phase 6: User Story 4 - 문서가 현재 상태와 일치한다 (Priority: P3)

- [X] T022 [US4] `README.md`: 7행 "## 세 가지 지표" → "## 지표"; 22행 "선택 권역은 붉은 줄, " 삭제; 24행 "**권역 지도**: 선택 권역만, " → "**통합 지도**: 세 권역을 한 화면에, "; 70행 "Jeddah 공항 실시간 운항정보 — 공식 페이지 404, FlightRadar24는 봇 차단"을 "Jeddah 공항 실시간 운항정보 페이지 — 404"로 좁히고, "## 시도했지만 버린 것" 앞에 "## 실험 중" 섹션을 추가해 FlightRadar24 비공식 피드(홍해 회랑 항공편 수, 같은 시각 평시, 차단 시 제거 원칙, OpenSky 기각 사유)를 기술. 표에 "홍해 상공 회피(실험)" 행 추가. (FR-019)
- [X] T023 [US4] quickstart.md §4 grep → "선택 권역"·"세 가지 지표" 0건, FlightRadar24는 "실험 중"에만.

---

## Phase 7: Polish

- [ ] T024 최종 확인: `python3 scripts/fetch_data.py` 정상 실행 → `node --check app.js` → quickstart §1·§3 재실행 → 커밋 → `git pull --rebase && git push` → Actions 1회 녹색(특히 FR24가 Actions IP에서 200인지 로그 확인; 막히면 research.md A5 원칙대로 flights 제거를 별도 커밋으로) → Pages에서 §3 반복.

---

## Dependencies & Execution Order

- **T001 → T002**: 이후 전부 T002에 의존(`last_ok_at`, 가드).
- **US1 (T003-T008)**: T003·T004·T005·T006은 같은 파일이라 순차. T007은 app.js라 US1 안에서 독립. T008은 T003-T007 뒤.
- **US2 (T009-T012)**: T009·T010 같은 파일 순차. T011은 [P]. T012는 T009-T011 뒤.
- **US3 (T013-T021)**: T013은 T002의 `last_ok_at`에 의존. T013-T015·T017-T020은 모두 app.js라 순차. T016은 [P]. T021은 T013-T020 뒤.
- **US4 (T022-T023)**: 언제든. T022는 README만.
- **T024**: 전부 뒤.

### Parallel Opportunities

- T011(update.yml), T016(index.html), T022(README.md)는 다른 어떤 태스크와도 동시에 가능.
- US1의 fetch_data.py 작업(T003-T006)과 US3의 app.js 작업(T013-T020)은 파일이 달라 병렬 가능하나, 한 사람이 하면 US1 → US2 → US3 순서가 검증 흐름상 자연스럽다.

---

## Implementation Strategy

**MVP = US1 + Foundational**: T001-T008만으로도 배지가 정직해진다. 그 상태로 커밋해도 된다.

권장 순서: Setup → Foundational → US1 → US2(같은 파일 fetch_data.py를 이어서) → US3 → US4 → Polish. 총 24개, 코드 변경은 5개 파일 안에서 끝난다.
