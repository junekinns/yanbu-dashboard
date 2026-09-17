# Implementation Plan: 도시 단위 재편 · 뉴스 파생 신호 중심으로

**Branch**: `003-city-signals` (main 직접 반영) | **Date**: 2026-09-17 | **Spec**: ./spec.md

**Input**: `specs/003-city-signals/spec.md` — 권역 타일 그리드를 도시 현황표 하나로 바꾸고, 그래프 타일(위성·해상·공지)을 걷어내며, 뉴스·후티 채널·외교부에서 파생 신호 3종(도시별 사건 템포, 단계 변경 감지, 후티 표적 언급)을 만든다. FAA NOTAM은 비밀값이 있을 때만 켜지는 선택 항목.

## Summary

수집 쪽은 "스냅샷"에서 "누적 이력"으로 바뀐다: 사건(30일)·후티 메시지(14일)·외교부 단계 변경(90일)을 `data/latest.json` 안에 누적하고, 그 이력에서 도시별 7일/이전 7일 건수·7일 언급 수·변경 목록을 계산해 내보낸다. 해상 교통 수집과 위성·공지의 평시/타일 계산은 제거한다. 화면은 헤드라인(단계 변경·출국권고 도시·공지 건수) + 도시 현황표 + 사건 로그 + 후티 채널(순위 + 메시지) + 지도 + 공지 + 뉴스 + 실험 영역 순. Google News RSS가 최대 100건이라 14일 시드는 국문 쿼리에서만 ~9일이 채워지고 영문은 하루치라, "지난주 대비"는 정직하게 2주 누적 뒤에만 표시한다.

## Technical Context

**Language/Version**: Python 3.12 (수집), 바닐라 JS + Leaflet 1.9 + Chart.js 4 (프론트 — Chart.js는 실험 타일 하나에만 남음)

**Primary Dependencies**: `requests`. 추가 없음. NOTAM은 같은 `requests`로 헤더 인증.

**Storage**: `data/latest.json` 단일 파일. 이력(사건 30일·메시지 14일·단계 변경 90일)도 이 파일 안. 예상 크기 ~150KB(해상 37KB·위성 일별/이력 제거로 상쇄).

**Testing**: 자동화 스위트 없음. (a) `fetch_data.py` 실행 후 JSON 불변식 스크립트(표 숫자 == 이력 직접 집계), (b) 소스 실패 주입, (c) Playwright 텍스트·스크린샷, (d) Actions 로그 — 002에서 확립한 방식 그대로.

**Target Platform**: GitHub Pages(정적) + GitHub Actions(매시간 cron, 2026-09-16 저녁부터 실제 발화 확인)

**Project Type**: 단일 정적 웹사이트 + 수집 스크립트

**Constraints**: 무료. 키는 서버 측(Actions secrets)만 허용, 페이지·저장소 파일에 절대 노출 금지. 새 파일·새 의존성 금지. "없는 비교를 0으로 꾸미지 않는다."

**Scale/Scope**: 개인/가족. 변경 파일 5개(`scripts/fetch_data.py`, `app.js`, `index.html`, `style.css`, `.github/workflows/update.yml`) + README. 대략 +350 / −250 LOC.

## Constitution Check

`.specify/memory/constitution.md`는 템플릿 상태. 프로젝트가 지켜온 원칙을 게이트로:

| 원칙 | 이번 계획 | 판정 |
|---|---|---|
| 무료·무키(페이지 노출 금지) | NOTAM 키는 Actions secret → env → 스크립트. 로그·JSON·페이지에 기록 안 함 | PASS |
| 오버엔지니어링 금지 | 새 파일 0, 새 추상화는 "이력 병합" 헬퍼 하나(`merge_history`)를 사건·메시지가 공유 | PASS |
| 수집 실패만 뜨는 지표 금지 | NOTAM은 키 없으면 "비활성"(실패 아님)으로 섹션 자체가 없음 | PASS |
| 의미 없는 지표 금지 | 해상·위성 타일·공지 그래프 제거. 남는 숫자는 전부 사용자가 신뢰하는 소스의 파생 | PASS |
| 정직한 표시 | 이력 14일 미만이면 비교를 표시하지 않음(FR-017) | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/003-city-signals/
├── plan.md              # 이 파일
├── research.md          # 실측 근거 + 결정
├── data-model.md        # latest.json 스키마(재편 후)
├── quickstart.md        # 검증 절차
└── tasks.md             # /speckit-tasks 가 생성
```

### Source Code (repository root)

```text
scripts/fetch_data.py          # 제거: maritime, REGIONS, firms 일별/평시. 추가: 이력 병합, mofa 변경 감지, 사건 템포, 후티 언급, NOTAM(선택)
app.js                         # 제거: 권역·타일 렌더러. 추가: 헤드라인, 도시 현황표(정렬·클릭→지도), 후티 순위. 지도는 places 기반 유지
index.html                     # 타일 섹션 → 헤드라인 + 표. 로그인 링크 삭제. 도움말·푸터 갱신
style.css                      # 표 스타일(모바일 열 접기), 권역·타일 CSS 삭제
.github/workflows/update.yml   # Fetch 스텝에 FAA secrets env 주입
README.md                      # 지표 표 재작성, 제거 사유
data/latest.json               # 산출물(스키마는 data-model.md)
```

**Structure Decision**: 기존 파일 내부 수정만. 시드 실행(14일 사건)은 환경변수 `EVENT_DAYS=14`로 로컬 1회 실행해 커밋 — 별도 스크립트 없음.

## 변경 설계

### 수집 (`scripts/fetch_data.py`)

**제거**
- `fetch_maritime`, `portwatch_rows`, `PORTWATCH_BASE`, `FETCHERS["maritime"]`. PLACES의 `port` 필드는 남겨도 무해하나 출력에서 뺀다.
- `REGIONS`, 출력 `regions`. PLACES의 `region`도 출력에서 뺀다(내부 사전에는 남겨도 됨).
- `fetch_firms`의 일별 집계·history·baseline·tier. 남는 것: 사우디 박스 화점 + 상시 플레어 필터 + `hotspots`(최근 7일, 최대 500건). 출력은 `{ok, hotspots}`.

**공통 헬퍼**
- `merge_history(prev_list, new_list, key, keep_days, date_of)`: 키 기준 병합(새 값이 기존을 갱신), `keep_days` 밖 제거, 날짜 내림차순 정렬. 사건·메시지가 공유.

**외교부 (`fetch_mofa(previous)`)** — FR-010~012
- 현재 `places[].level`을 `previous.places`와 비교. 둘 다 숫자이고 다르면 `changes`에 `{city, from, from_name, to, to_name, at}` 추가. `changes`는 `previous.changes`에 이어 붙이고 `at` 기준 90일 유지.
- `tracking_since`: previous 값이 있으면 유지, 없으면 이번 `fetched_at`.
- 실패 시 함수가 일찍 반환하므로 비교 자체가 없다(FR-011). `carry_over`가 `changes`·`tracking_since` 보존.
- `weekly_counts`는 더 이상 화면에 없으니 출력에서 빼고 `last7d`·`baseline`만 남긴다(헤드라인 숫자).

**사건 (`fetch_events(previous)`)** — FR-016~019
- 검색 범위 `when:{EVENT_DAYS}d`, `EVENT_DAYS = int(os.environ.get("EVENT_DAYS", "3"))`.
- 클러스터 → 항목(키 `date|city|type`) → `merge_history(previous.events, new, keep_days=30)`; 병합 시 `outlets`는 max, `time/iso`는 더 이른 것, 제목은 기존 유지(대표 기사 안 흔들리게).
- `tempo`: 도시별 `{"7d": {type: n}, "prev7d": {type: n} | None, "total7d": n}`; `history_days = (오늘 − min(date)) + 1`; `prev7d`는 `history_days >= 14`일 때만. 창 기준은 사우디 현지 날짜(`date` 필드).
- 출력: `events`(이력 전체, 최신순), `tempo`, `history_days`, `history_since`.

**후티 (`fetch_telegram(previous)`)** — FR-013~015
- 필터(사우디 지명 또는 "السعود|Saudi")를 통과한 메시지를 `merge_history(previous.messages, new, key=url, keep_days=14)`.
- 번역: 이력 중 `text_ko`가 없고 최신 6건 안에 드는 것만 MyMemory 호출(캐시는 이력 자체가 대신함).
- `mentions7d`: 최근 7일 메시지에서 `places`를 `set`으로 세어 도시별 합 → `{city: n}` 내림차순.
- 출력: `messages`(이력, 최신순), `mentions7d`.

**NOTAM (`fetch_notams(previous)`)** — FR-020~022
- `cid, sec = os.environ.get("FAA_CLIENT_ID"), os.environ.get("FAA_CLIENT_SECRET")`. 없으면 `{"ok": True, "enabled": False, "fetched_at": ...}` 반환(`safe`가 `last_ok_at`을 찍어도 무해).
- 있으면 `GET https://external-api.faa.gov/notamapi/v1/notams?icaoLocation={L}&responseFormat=geoJson&pageSize=100` (헤더 `client_id`, `client_secret`) × `["OEJN","OERK","OEDF","OEMA","OEJD"]`. 응답의 `items[].properties.coreNOTAMData.notam` 에서 `number, effectiveStart, effectiveEnd, text, location`을 읽는다(정확한 경로는 키 수령 후 첫 응답으로 확정 — research.md §5).
- 분류: 텍스트 정규식 `AIRSPACE|CLSD|CLOSED|RESTRICTED|PROHIBITED|DANGER|MISSILE|ROCKET|FIRING|UAS|DRONE|GPS.*(INTERFER|JAM)` 매치만 유지, `kind`는 첫 매치 그룹으로. 출력 `{ok, enabled: True, items: [...]}`.
- 로그 한 줄에 키 값이 절대 안 찍히게: 오류 메시지에서 헤더는 원래 포함되지 않지만, `error` 문자열에 URL만 들어가도록 `requests` 예외 메시지를 그대로 쓴다(URL에 키 없음).

**main**
- `FETCHERS`에서 `maritime` 제거, `notams` 추가. 출력에서 `regions` 제거.

### 화면 (`index.html`, `app.js`, `style.css`)

- **제거**: `#tile-mofa`, `#region-tiles`, `renderMofaTile/renderRegionTiles/regionBadge/REGION_KEYS/regionName/fillTile의 지역 호출`, `#workflow-link`, 권역·타일 CSS. `fillTile`/`sparkline`은 실험 타일 하나를 위해 남긴다.
- **헤드라인 `#headline`** (기존 `#mofa-line` 자리): 세 문장 — ① "출국권고: 얀부 · 주베일 · … (N곳) · 그 외 특별여행주의보" ② "최근 변경: 제다 특별여행주의보→출국권고 (9/16)" 최대 3건 또는 "최근 30일 단계 변경 없음 (추적 시작 9/17)" ③ "이번 주 외교부 공지 7건 (평시 1.5건)". 각 문장은 `<p>`.
- **도시 현황표 `#city-table`**: 행 = `mofa.places`(좌표 있는 것). 열 = 도시 | 외교부 단계(dot+라벨, 30일 내 변경 있으면 `▲ 9/16` 배지) | 경보 | 요격 | 피격 | 공습 | 지난주 | 후티 7일. 값 0은 `—`, >0은 유형 색 배지. "지난주" 열: `prev7d`가 있으면 `total7d vs prev_total`을 "▲ +2" / "▼ −1" / "="로, 없으면 "이력 N일째"를 열 머리글 아래 한 번만 표기하고 칸은 `—`. 정렬 FR-007. 모바일(≤700px)은 유형 4열을 숨기고 "사건" 합계 1열로 대체(CSS `display:none` + JS가 합계 셀을 항상 렌더).
- **클릭→지도**: `renderMap`이 도시 마커를 `state.markers[name]`에 보관; 행 클릭 시 `state.map.flyTo([lat,lon], 8)` 후 `openPopup()`. 지도 카드까지 스크롤(`scrollIntoView`).
- **사건 로그**: `events.events`를 72h로 필터(기존). 권역 배지 제거.
- **후티 섹션**: 상단에 `mentions7d` 순위 칩("카미스무샤이트 4 · 얀부 2") + "상대측 발표 · 검증되지 않음". 목록은 최신 6건.
- **지도**: `places` 기반 유지. 팝업에서 항만 줄 제거, 최근 7일 사건 수 표기. 화점 레이어·범례 유지. 초기 bounds = places 좌표.
- **NOTAM 섹션**: `data.notams?.enabled`일 때만 DOM에 추가(정적 마크업 없이 JS가 카드 생성) — 비활성 시 흔적 0.
- **실험 영역**: 홍해 상공 회피 타일을 페이지 하단 "실험" 카드로 이동(기존 마크업 재사용).
- **도움말/푸터**: 지표 정의를 파생 신호 3종 + 화점 레이어로 다시 씀. 출처에서 PortWatch 제거, NOTAM 활성 시에만 "FAA NOTAM" 표기.

### 워크플로우

- Fetch 스텝에 `env: FAA_CLIENT_ID: ${{ secrets.FAA_CLIENT_ID }}`, `FAA_CLIENT_SECRET: ${{ secrets.FAA_CLIENT_SECRET }}`. 비밀값이 없으면 빈 문자열 → 스크립트가 비활성 처리.

## 작업 순서

1. 수집 제거(해상·권역·위성 타일) → 이력 병합 헬퍼 → 사건 이력/템포 → 후티 이력/언급 → 외교부 변경 → NOTAM(비활성 경로) → 로컬 실행 + 불변식
2. 화면: 마크업 정리 → 헤드라인 → 도시 현황표 → 후티 순위 → 지도 팝업/클릭 → 실험 영역 이동 → CSS → Playwright
3. 워크플로우 env, README
4. `EVENT_DAYS=14`로 1회 시드 실행 → 커밋 → push → Actions 1회 확인 → Pages 확인

## Complexity Tracking

위반 없음.
