---

description: "Task list for 도시 단위 재편 · 뉴스 파생 신호 중심으로"
---

# Tasks: 도시 단위 재편 · 뉴스 파생 신호 중심으로

**Input**: Design documents from `/specs/003-city-signals/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: 자동화 스위트 없음. 스토리마다 quickstart.md 해당 절을 실행하는 검증 태스크.

**Scope rule**: 새 파일·새 의존성 없음. 변경 파일: `scripts/fetch_data.py`, `app.js`, `index.html`, `style.css`, `.github/workflows/update.yml`, `README.md`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일, 선행 없음. 같은 파일을 만지는 태스크끼리는 [P] 없음.
- **[Story]**: US1 도시 현황표(P1) / US2 단계 변경(P1) / US5 제거(P1) / US3 후티 언급(P2) / US4 사건 템포(P2) / US6 NOTAM(P3)

## Path Conventions

단일 정적 웹사이트, repo root 기준. 위치는 함수명으로 표기(002 이후 줄 번호가 움직였음).

---

## Phase 1: Setup

- [X] T001 스크래치 venv로 `python3 scripts/fetch_data.py` 1회 실행해 재편 전 `data/latest.json`을 확보(이력 병합의 `previous`가 됨), `node --check app.js` 통과 확인

---

## Phase 2: Foundational (스키마 정리 + 공용 헬퍼)

**Purpose**: 모든 스토리가 기대는 "제거된 스키마"와 "이력 병합" 한 조각. 여기까지 끝나면 수집이 다시 정상 실행돼야 한다.

- [X] T002 `scripts/fetch_data.py`: `fetch_maritime`·`portwatch_rows`·`PORTWATCH_BASE` 삭제, `FETCHERS`에서 `maritime` 제거, `REGIONS` 상수와 `main()`의 `regions` 출력 삭제, `fetch_mofa`의 `places` 출력에서 `region`·`port` 제거. 파일 docstring(상단 6줄 목록)에서 maritime 줄 삭제. (FR-002, FR-003)
- [X] T003 `scripts/fetch_data.py` `fetch_firms`: 권역 루프·`daily_counts`·`history`·`baseline`·`tier` 제거. 상시 플레어 필터는 유지하고 `hotspots`(사우디 박스, 날짜순 최근 500건)만 출력. `previous` 인자는 시그니처 유지(`FETCHERS` 호출 규약). (FR-004)
- [X] T004 `scripts/fetch_data.py`: 공용 헬퍼 `merge_history(prev, new, key, keep_days, day_of, update=None)` 추가 — `key(item)`로 dict 병합(새 항목이 기존을 덮되 `update(old, new)`가 있으면 그 결과 사용), `day_of(item)`이 `keep_days` 밖이면 제거, `day_of` 내림차순 리스트 반환. `TODAY_AST = datetime.now(AST).date()` 상수 추가(창 계산 기준).
- [X] T005 T002~T004 반영 후 `python3 scripts/fetch_data.py` 실행 → 7개 소스 중 maritime 제외 6개 ok, JSON에 `regions`/`maritime` 없음 확인

**Checkpoint**: 제거된 스키마로 수집이 성공한다

---

## Phase 3: User Story 5 - 그럴싸하기만 한 것을 걷어낸다 (Priority: P1)

**Goal**: 방문자 화면에서 로그인 링크·권역·타일 그래프 제거, 화점 레이어와 공지 숫자만 유지

**Independent Test**: quickstart §3의 `LEFTOVER` 검사 0건 + 화점 범례 유지

- [X] T006 [P] [US5] `index.html`: `#workflow-link` 앵커 삭제; `<section class="tiles">`(공지 템포·홍해 상공 타일)와 `<section id="region-tiles">` 삭제; 그 자리에 `<section class="card" id="headline-card"><div id="headline"></div></section>`와 `<section class="card"><h2>도시 현황</h2><table id="city-table">…</table><p class="muted small" id="city-note"></p></section>` 마크업; 페이지 하단(언론 보도 뒤)에 `<section class="card experimental" id="lab">` 안에 기존 `#tile-flights` 마크업 이동; `#mofa-line` 제거(헤드라인이 대체); `tiles-help`의 내용을 파생 신호 3종 + 화점 레이어 정의로 재작성; 사건 로그 각주에서 권역 언급 제거; 푸터 출처에서 IMF PortWatch 삭제. (FR-001, FR-002, FR-004, FR-005)
- [X] T007 [P] [US5] `style.css`: `.region-*`, `.region-tiles`, `.region-heading`, `.region-tile-row`, `.tile h3`, `.tiles` 그리드 규칙 삭제(`.tile`/`.badge`/`.exp-badge`는 실험 타일용으로 유지). `#lab`용 최소 스타일.
- [X] T008 [US5] `app.js`: `REGION_KEYS`/`regionName`/`regionCls`/`regionBadge`, `renderMofaTile`, `renderRegionTiles`, `levelDot`·기존 `renderHeader`의 경보 한 줄 부분 삭제(공지 목록 렌더는 `renderNotices`로 분리). `renderEvents`·`renderTelegram`에서 권역 배지 제거. `renderMap` 팝업에서 항만 줄(`series`/`port`) 제거, `regionName` 호출 제거. `renderAll`을 `renderHeadline(); renderCityTable(); renderEvents(); renderTelegram(); renderNotices(); renderMap(); renderFlightsTile();`로(뒤 셋은 이후 태스크에서 구현되므로 이 시점엔 빈 함수 stub 허용 안 함 — T012·T014와 함께 커밋). (FR-001~005)

**Checkpoint**: T006~T008 + T012·T014 완료 시점에 페이지가 오류 없이 뜬다

---

## Phase 4: User Story 2 - 단계 변경을 놓치지 않는다 (Priority: P1)

**Goal**: 외교부 단계 변경 이력 + 헤드라인 표시

**Independent Test**: quickstart §2b(주입 변경 감지), §2c(실패 시 가짜 변경 없음)

- [X] T009 [US2] `scripts/fetch_data.py` `fetch_mofa()` → `fetch_mofa(previous)`(`FETCHERS["mofa"]`도 직접 전달로): 성공 경로 끝에서 `prev_levels = {p["name"]: p["level"] for p in previous.get("places", [])}`; 현재 places 중 이전·현재 `level`이 모두 숫자이고 다르면 `{"city", "from", "from_name", "to", "to_name", "at": now_iso()}`를 새 변경으로; `changes = merge_history(previous.get("changes", []), new, key=lambda c: (c["city"], c["at"]), keep_days=90, day_of=lambda c: c["at"][:10])`; `tracking_since = previous.get("tracking_since") or fetched_at`; 출력에 `changes`, `tracking_since` 추가, `weekly_counts` 제거. (FR-010~012)
- [X] T010 [US2] `app.js` `renderHeadline()`: `#headline`에 `<p>` 3개 — ① `level>=3` 도시를 정렬 키 순으로 "출국권고: 얀부 · 주베일 · … (N곳) · 그 외 <최빈 단계>" ② `changes` 중 30일 이내 최신 3건을 "최근 변경: 제다 특별여행주의보→출국권고 (9/16)" 형식, 없으면 "최근 30일 단계 변경 없음 (추적 시작 M/D)" ③ "이번 주 외교부 공지 N건 (평시 B건) · <tier>". `staleTag(mofa)` 부착. (FR-012, FR-005)
- [X] T011 [US2] quickstart §2b·§2c 실행 → 주입 변경 1건 감지, 실패 실행에서 `changes` 길이 불변. 검증 뒤 정상 실행으로 원복하고 인위적 변경 1건은 `data/latest.json`의 `changes`에서 제거

**Checkpoint**: 단계 변경이 데이터와 헤드라인에 나타난다

---

## Phase 5: User Story 1 - 도시 한 줄로 상황을 읽는다 (Priority: P1) 🎯 MVP

**Goal**: 도시 현황표(정렬·0은 —·변경 배지·클릭→지도·모바일)

**Independent Test**: quickstart §3 rows/정렬/popup/mobile overflow

- [X] T012 [US1] `app.js` `renderCityTable()`: 행 = `mofa.places`; 각 행에 `tempo[city]`(없으면 0)와 `mentions7d[city]`(없으면 0), 30일 내 최신 변경; 정렬 `(-level, -total7d, name)`(FR-007); 셀: 도시(`<button class="city-link" data-city>`), 단계(dot+라벨, 변경 있으면 `<span class="chg">▲ M/D</span>`), 경보·요격·피격·공습(0→`—`, >0→`.ev-type` 색 배지), 사건 합계(모바일용, 항상 렌더), 지난주(`prev7d` 있으면 `▲ +n`/`▼ −n`/`=`, 없으면 `—`), 후티 7일(0→`—`). `#city-note`: `history_days < 14`면 "사건 이력 N일째 — 지난주 대비는 14일부터 표시" 아니면 "최근 7일 vs 이전 7일". (FR-006~008)
- [X] T013 [US1] `app.js`: `renderMap`에서 도시 마커를 `state.markers[name]`에 보관(레이어 재생성 시 갱신); `#city-table` 클릭 위임 — `.city-link`면 `state.map.flyTo([lat, lon], 8)`, 마커 `openPopup()`, `#map` 카드로 `scrollIntoView({behavior: "smooth"})`. 팝업 내용: 도시 · 단계 · 최근 7일 사건 N건 · 후티 언급 N회. (FR-009)
- [X] T014 [US1] `app.js`: `renderNotices()`(기존 공지 목록 코드 이동), `setLastUpdated`·`refresh`·`main`이 새 `renderAll`과 맞는지 정리. `combinedBounds(places)`만 남김(regions 인자 제거).
- [X] T015 [P] [US1] `style.css`: `.city-table`(전체 폭, 행 구분선, 숫자 열 우측 정렬, `.city-link` 버튼 리셋), `.chg` 배지, `.up/.down/.flat` 색; `@media (max-width: 700px)`에서 유형 4열(`.col-type`)과 지난주 열 숨기고 합계 열(`.col-total`) 표시, 데스크톱은 반대.
- [X] T016 [US1] `node --check app.js` → 정적 서버 → quickstart §3 실행(rows·headline·popup·mobile overflow·errors)

**Checkpoint**: 표 하나로 도시 상황이 읽힌다 — 여기까지가 MVP

---

## Phase 6: User Story 4 - 사건 템포 (Priority: P2)

**Goal**: 사건 이력 누적(30일) + 도시별 7일/이전 7일 집계

**Independent Test**: quickstart §1 템포 불변식, §2a 중복 없음

- [X] T017 [US4] `scripts/fetch_data.py` `fetch_events()` → `fetch_events(previous)`: `EVENT_DAYS = int(os.environ.get("EVENT_DAYS", "3"))`로 두 쿼리의 `when:3d`를 치환; 클러스터 결과를 `merge_history(previous.get("events", []), new, key=lambda e: (e["date"], e["city"], e["type"]), keep_days=30, day_of=lambda e: e["date"], update=lambda old, new: {**old, "outlets": max(old["outlets"], new["outlets"]), **({"time": new["time"], "iso": new["iso"]} if new["iso"] < old["iso"] else {})})`; `[:15]` 캡 제거. (FR-016, FR-018, FR-019)
- [X] T018 [US4] `scripts/fetch_data.py` `fetch_events`: `today = TODAY_AST`; `w7`/`p7` 날짜 집합; `tempo[city] = {"7d": Counter by type, "total7d", "prev7d": ... if history_days >= 14 else None, "prev_total": ... or None}` — 도시는 `PLACES` 중 좌표 있는 전부(사건 0인 도시도 키 존재); `history_days = (today − min(date)).days + 1`(이력 없으면 0); 출력 `tempo`, `history_days`, `history_since`, `today`. (FR-017)
- [X] T019 [US4] quickstart §1 템포 불변식 + §2a 두 번 실행 중복 없음 확인

**Checkpoint**: 표의 사건 숫자가 이력과 100% 일치

---

## Phase 7: User Story 3 - 후티 표적 언급 (Priority: P2)

**Goal**: 메시지 이력(14일) + 7일 언급 순위

**Independent Test**: quickstart §1 언급 불변식, §3 mentions 텍스트

- [X] T020 [US3] `scripts/fetch_data.py` `fetch_telegram(previous)`: 필터 통과 메시지를 `merge_history(previous.get("messages", []), new, key=lambda m: m["url"], keep_days=14, day_of=lambda m: m["iso"][:10], update=lambda old, new: {**new, "text_ko": old.get("text_ko")})`; 번역은 병합 결과 최신 6건 중 `text_ko`가 없는 것만(기존 캐시 로직 대체); `mentions7d`: `iso >= now−7d`인 메시지의 `set(places)` 합산 → 내림차순 dict; 출력 `messages`(이력), `mentions7d`. (FR-013, FR-014)
- [X] T021 [US3] `app.js` `renderTelegram()`: 목록 위에 `<div id="tg-mentions">` — `mentions7d`를 "카미스무샤이트 4 · 얀부 2 · 제다 1" 칩으로, 비면 "최근 7일 사우디 도시 언급 없음", 항상 뒤에 "상대측 발표 · 검증되지 않음"; 목록은 `messages.slice(0, 6)`. (FR-014, FR-015)
- [X] T022 [US3] quickstart §1 언급 불변식 + §3 `mentions` 출력 확인

**Checkpoint**: 후티 순위가 표의 후티 열과 일치

---

## Phase 8: User Story 6 - NOTAM 선택 항목 (Priority: P3)

**Goal**: 비밀값 있을 때만 켜지는 NOTAM 수집·표시. 이번 배포에서는 비활성 경로만 검증.

**Independent Test**: quickstart §1 `notams.enabled is False`, §3 `notam section: false`

- [X] T023 [US6] `scripts/fetch_data.py` `fetch_notams(previous)`: env `FAA_CLIENT_ID`/`FAA_CLIENT_SECRET` 없으면 `{"ok": True, "enabled": False, "fetched_at": now_iso()}`; 있으면 `NOTAM_LOCATIONS = ["OEJN","OERK","OEDF","OEMA","OEJD"]` 각각 `get(f"https://external-api.faa.gov/notamapi/v1/notams?icaoLocation={loc}&responseFormat=geoJson&pageSize=100", headers={**HEADERS, "client_id": cid, "client_secret": sec}, timeout=30).json()`; `items = data.get("items", [])`, 각 `props = it.get("properties", {}).get("coreNOTAMData", {}).get("notam", {})`; `text = props.get("text", "")`; 정규식 `NOTAM_KINDS = [("공역 폐쇄", r"AIRSPACE.*(CLSD|CLOSED)|CLOSED.*AIRSPACE"), ("제한/금지", r"RESTRICTED|PROHIBITED|QRTCA|QRPCA|QRRCA"), ("위험구역", r"DANGER|QRDCA"), ("사격/미사일", r"MISSILE|ROCKET|FIRING|GUN"), ("UAS", r"UAS|DRONE"), ("GPS 간섭", r"GPS.*(INTERFER|JAM)|GNSS")]` 첫 매치를 `kind`로, 매치 없으면 제외; 출력 `{ok, enabled: True, locations, items: [{location, number, effective_start, effective_end, kind, text[:200]}]}`. `FETCHERS["notams"]` 추가. 키 값이 `error`·로그에 안 들어가는지 확인. (FR-020~022)
- [X] T024 [P] [US6] `.github/workflows/update.yml` "Fetch data" 스텝에 `env: FAA_CLIENT_ID: ${{ secrets.FAA_CLIENT_ID }}` / `FAA_CLIENT_SECRET: ${{ secrets.FAA_CLIENT_SECRET }}`.
- [X] T025 [US6] `app.js` `renderNotams()`: `data.notams?.enabled`일 때만 `#lab` 앞에 `<section class="card" id="notam">` 생성 — 제목 "사우디 공역 NOTAM", `items` 없으면 "현행 공역 제한 NOTAM 없음", 있으면 `location · kind · effective_start~end · text`; 푸터 출처에 "FAA NOTAM" 동적 추가. 비활성이면 DOM에 아무것도 없음. `renderAll`에 추가. (FR-020)
- [X] T026 [US6] 비밀값 없는 로컬 실행 → `notams.enabled false`, 페이지에 `#notam` 없음(quickstart §1·§3)

**Checkpoint**: 키 없이도 완결, 키가 오면 §5로 켠다

---

## Phase 9: Polish

- [X] T027 [P] `README.md`: 지표 표를 "도시 현황표(외교부 단계·7일 사건·지난주 대비·후티 언급) / 단계 변경 이력 / 후티 표적 순위 / 지도(도시·사건·위성 화점)"로 재작성; 해상 교통·위성 타일·공지 그래프 제거 사유(사용자 지적 인용: 며칠에 한 번 바뀌는 그래프는 장식); "실험 중"에 NOTAM(키 대기) 추가; PortWatch를 "버린 것"으로 이동(5일 지연). (FR-024)
- [X] T028 (배포 완료: 커밋 1166902, run 35173674126 성공. 러너에서 외교부만 연결 타임아웃으로 stale 처리됐고 places·changes 보존 확인 — 그레이스풀 디그레이드 동작) `EVENT_DAYS=14 python3 scripts/fetch_data.py` 1회 시드 → quickstart §1 재실행 → `node --check app.js` → 커밋 → `git pull --rebase -X theirs origin main && git push` → `gh workflow run update.yml` → 실행 로그에 `notams: ok=True`·나머지 ok·총 30초 이내 확인 → Pages에서 §3 반복

---

## Phase 10: 배포 후 추가 (US7 표 간소화 · US8 위기 단계) — 2026-09-17

- [X] T029 [US8] `scripts/fetch_data.py`: `PINNED`·`CRISIS_LEVELS` 상수, `crisis_summary(output, previous)` — FR-026 규칙대로 점수·reasons·일별 history(90일) 계산; `main()`에서 모든 소스 수집 뒤 `output["summary"]`로, 예외 시 이전 summary + stale. 로그 한 줄 `summary: level= score= reasons=`.
- [X] T030 [US8] `index.html` `#crisis` 섹션(헤더, 부제 아래) + 도움말에 규칙 전문; `app.js` `renderCrisis()`(큰 숫자·라벨·근거 목록·7일 띠); `style.css` `.crisis` (단계별 색 변수 `--lv`, 모바일 축소).
- [X] T031 [US7] `app.js` `renderCityTable()`: `summary.pinned` ∪ 움직임 있는 도시만 기본 표시, 나머지는 `tr.more`의 `.quiet-toggle`로 접기/펼치기(`state.showQuiet`); `index.html` 카드 부제·도움말 갱신; `style.css` 토글·quiet 행.
- [X] T032 검증: 로컬 실행 → `summary.level=4 심각, score 7, reasons 5`; Playwright — 배너 텍스트에 근거 5줄, 표 8행 + 토글 → 20행, 모바일 overflow 없음, 오류 0.

## Phase 11: 컴팩트화 + 사건 아이콘 — 2026-09-17 ("과하게 하지 말라. 알짜배기만.")

- [X] T033 텍스트 제거: 부제 문장, 도움말 `<details>` 블록, 사건·후티·실험 각주 문장, 푸터 안내문 축약. 위기 배너 근거를 5줄 목록 → 한 줄 칩, "자체 기준" 명시. 헤드라인 3줄 → 1줄. 조용한 도시 토글 제거(표에는 주요 5곳 + 움직임 있는 도시만, 나머지는 지도 점). 후티 메시지 6 → 5건, 원문 `<details>` 대신 번역 실패 시에만 원문.
- [X] T034 지도 간결화: 표에 있는 도시만 이름 라벨, 나머지는 작은 점. 범례 축약(단계 항목 제거).
- [X] T035 사건 아이콘: `fetch_data.py`에 `WEAPON_PATTERNS`(드론/미사일, 기사 제목 기준)로 `events[].weapon` 추가(이력 병합 시 보존). `app.js` `L.divIcon` SVG — 모양 = 무기(미사일/드론/기타), 색 = 유형, 6시간 이내 pulse. 궤적·경로 시뮬레이션은 데이터가 없어 하지 않음(README에 명시).

## Dependencies & Execution Order

- T001 → T002~T004(같은 파일, 순차) → T005 검증 → 이후 스토리.
- **US5 프론트(T006·T007 [P], T008)**와 **US1(T012~T014)**은 `app.js`가 한 번에 정합해야 페이지가 뜨므로 T008→T012→T013→T014를 이어서 하고 T016으로 검증. T006·T007·T015는 병렬 가능.
- **US2(T009~T011)**: T009는 fetch_data.py(T004 뒤), T010은 app.js(T008 뒤). 
- **US4(T017~T019)**, **US3(T020~T022)**: 수집은 fetch_data.py 순차(T009→T017→T020), 프론트는 T021만 app.js.
- **US6(T023~T026)**: T023 fetch_data.py 마지막, T024 [P], T025 app.js 마지막.
- T027 [P] 언제든. T028 전부 뒤.

### Parallel Opportunities

- T006(index.html), T007·T015(style.css), T024(update.yml), T027(README)는 서로 및 다른 태스크와 병렬.
- fetch_data.py 계열(T002-T004, T009, T017-T018, T020, T023)과 app.js 계열(T008, T010, T012-T014, T021, T025)은 파일이 달라 병렬 가능하나, 한 사람은 수집→화면 순서가 검증 흐름상 자연스럽다.

---

## Implementation Strategy

**MVP = Foundational + US5 + US2 + US1 (T001~T016)**: 표·헤드라인·제거까지. 이 시점에 표의 사건 열은 3일치 이력(누적 시작)이고 후티 열은 0일 수 있으나 "이력 N일째" 표기로 정직하다. US4·US3이 이어서 열을 채우고, US6은 키가 없어도 비활성으로 완결.

한 번에 배포한다(사용자 지시 "바로바로 진행하고 배포"). 총 28개 태스크.
