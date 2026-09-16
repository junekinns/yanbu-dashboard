# Phase 0 Research: 신호 전수조사 · 지도 고도화 · 수동 갱신

## 1. 신규 신호 후보 (User Story 1)

Decision, rationale, alternatives는 실제 curl/요청 테스트 결과가 나오는 대로 이 표에 채운다 (fetch_data.py 조사 태스크와 병행). 현재 확정된 항목:

- **Decision**: 위성 열 감지(NASA FIRMS), 외교부 공지 템포(0404.go.kr), 해상 교통(IMF PortWatch)만 채택 유지.
- **Rationale**: 세 소스 모두 무료·무키·실제 응답 확인됨. FIRMS와 PortWatch는 사후 발표 이전에 나타나는 하드 데이터라는 점에서 "숨은 신호" 기준을 통과.
- **Alternatives considered**: ACLED, US State Dept travel advisory, UKMTO, GDELT — 모두 기각(무료 API 없음/응답 없음/신호가 이미 뉴스화된 사후 데이터). 기각 사유는 기존 메모리·README에 기록됨.

## 2. 기존 지표 재평가 (User Story 2)

- **Decision**: 위성 열 감지·해상 교통 유지, 공지 템포는 유지하되 "사후 반응" 성격을 UI 설명에 명시. 과거 관심도(Wikipedia pageviews) 지표는 이미 제거됨.
- **Rationale**: 사용자 피드백(“의미 없다”, “과하다”)에 따라 선행성이 약한 지표는 격하하고, 검증된 하드 데이터만 1급으로 유지.
- **Alternatives considered**: 시장 반응(아람코 주가) 지표 — 커밋 이력상 이미 추가했다가 철회됨(8e6bbd9). 재도입하지 않음.

## 3. 후티 채널 한글 우선 표시 (User Story 3)

- **Decision**: 무료 번역 API(비공식 Google Translate 엔드포인트 등)로 사전 번역해 `text_ko` 필드로 저장, 프론트는 `text_ko` 우선 노출 + 원문 `<details>` 접기. 이미 구현되어 있음(app.js:117-127).
- **Rationale**: 유료 키 없이 처리 가능, 실패 시 원문만 보여주는 그레이스풀 디그레이드 확보.
- **Alternatives considered**: 클라이언트 사이드 실시간 번역 — API 키/쿼터 노출 위험 및 응답 지연으로 기각.

## 4. 지도 고도화 (User Story 4)

- **Decision**: 실시간 궤적/3D는 기각(민간 무료 소스 없음). 위성 타일(Esri World Imagery) 토글은 채택·구현됨(app.js:76-79, 146-150).
- **Rationale**: Palantir AIP급 실시간 추적은 군사 기밀 영역이라 민간 무료 소스로 불가능(Assumptions에 명시). 위성뷰 토글은 무료 타일 서버로 실현 가능해 채택.
- **Alternatives considered**: WebGL 기반 3D 지구본(CesiumJS 등) — 번들 크기·복잡도 대비 이득 작아 기각("오버엔지니어링 금지" 제약).

## 5. 수동 갱신 (User Story 5)

- **Decision**: (a) 로그인 사용자용 GitHub Actions `workflow_dispatch` 링크, (b) 방문자용 캐시 무효화 강제 새로고침 버튼(`fetch(...,{cache:"no-store"})`) 두 갈래 모두 구현됨(index.html:19-23, app.js:238-260).
- **Rationale**: 정적 GitHub Pages는 버튼 클릭으로 즉시 서버 재계산이 불가능하므로, 두 갈래가 정적 사이트 제약 안에서의 현실적 최선.
- **Alternatives considered**: 서버리스 함수(예: Vercel/Cloudflare Workers)로 온디맨드 수집 — 새 인프라/키 필요, 제약(무료·무키·오버엔지니어링 금지)에 위배되어 기각.

## 6. 권역 탭 제거 · 한 페이지 통합 뷰 (User Story 6)

- **Decision**: 권역 탭(`#region-tabs`)을 제거하고, 지표 타일은 권역별 그리드로, 지도는 세 권역 bounding box를 합친 뷰로, 사건/채널 목록은 권역 배지로 표시한다.
- **Rationale**: 세 개의 독립된 Leaflet 지도 인스턴스를 만드는 대신 기존 지도 하나의 뷰포트만 넓히는 방식이 "오버엔지니어링 금지" 제약과 낮은 트래픽 규모(개인/가족 사용자)에 부합. `regions[].box`가 이미 데이터에 있어 `L.latLngBounds`로 합치기만 하면 됨.
- **Alternatives considered**:
  - 3개의 별도 Leaflet 지도(권역별 고정 뷰) — 로드·렌더 비용 3배, 반응형 레이아웃 복잡도 증가. 정보 밀도 이득 대비 과함.
  - 아코디언(권역별 접었다 펴기) — 탭과 본질적으로 동일한 클릭-후-확인 마찰이 남아 사용자 요구("탭으로 나누지 말고")를 충족하지 못함.
  - 지도는 유지하고 타일만 그리드화 — 탭을 없앤다면서 지도만 여전히 "선택된 권역" 개념을 남기는 것은 요구 사항(Acceptance Scenario 3)에 미달.
