# Quickstart: 신호 전수조사 · 지도 고도화 · 수동 갱신

## Prerequisites

- Python 3.12, Node(구문 검사용, `node -e`만 사용), 브라우저.
- 새 패키지 설치 불필요(기존 `requests` + CDN Leaflet/Chart.js만 사용).

## 1. 데이터 수집 검증 (User Story 1, 2)

```bash
python3 scripts/fetch_data.py
```

- **Expect**: `data/latest.json`이 갱신되고, `firms`/`mofa`/`maritime` 세 신호 모두 `error` 없이 실제 값(0건이 아닌 `daily_counts`/`weekly_counts`/`spark`)을 담는다.
- 신규 소스를 추가했다면 이 실행 로그에서 새 필드가 채워지는지 확인하고, 실패한 소스는 README "시도했지만 버린 것"에 기록한다.

## 2. 정적 서빙으로 프론트 확인

```bash
node -e "require('./app.js')" 2>&1 | head -5   # 구문 오류만 빠르게 확인(브라우저 API 호출은 무시하고 죽어도 정상)
python3 -m http.server 8000
```

브라우저로 `http://localhost:8000` 접속.

- **User Story 3 (후티 한글 우선)**: "후티 군 대변인 채널" 카드에서 한국어 문장이 기본으로 보이고, "아랍어 원문" `<details>`를 펼쳐야 원문이 보이는지 확인.
- **User Story 4 (지도 고도화)**: 지도 상단 "지도/위성" 토글을 눌러 위성 타일로 전환되는지 확인.
- **User Story 5 (수동 갱신)**: "↻ 새로고침" 버튼을 눌러 `data/latest.json`을 재요청하고 상태 메시지("이미 최신입니다" 또는 "새 데이터로 갱신했습니다")가 뜨는지 확인. "지금 바로 데이터 재수집" 링크는 GitHub 로그인 후 Actions 탭으로 이동하는지 확인.
- **User Story 6 (권역 통합 뷰)**:
  1. 헤더에 권역 탭 버튼이 **없어야** 한다.
  2. 지표 타일 섹션을 스크롤 없이/한 번의 스크롤로 보면 서부·중부·동부 각각의 위성 열 감지·해상 교통 타일이 모두 보이고, 공지 템포 카드는 전국 단일 카드로 1개만 있어야 한다.
  3. 지도를 로드하면 초기 뷰가 세 권역(얀부·제다 / 리야드 / 담맘·다란·주베일)을 모두 포함하도록 줌아웃되어 있어야 한다(특정 권역만 확대된 상태로 시작하면 실패).
  4. 사건 로그와 후티 채널 목록의 각 항목에 권역 배지(서부/중부/동부)가 붙어 있어야 한다.

## 3. 배포 후 확인

```bash
git add -A && git commit -m "..." && git push
```

- GitHub Actions "update.yml" 워크플로우 로그에서 `fetch_data.py` 실행이 성공했는지 확인(Actions 탭).
- GitHub Pages 배포 후 실제 URL에서 위 2번 체크리스트를 반복 확인.

## Reference

- 데이터 스키마: [data-model.md](./data-model.md)
- 채택/기각 근거: [research.md](./research.md)
