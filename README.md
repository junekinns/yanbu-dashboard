# Red Sea Watch · 얀부·제다

US Pizza Index처럼, 공식 발표가 말하지 않는 것을 간접 신호로 읽는 비공식 대시보드. 사우디아라비아 얀부·제다에 있는 한인 교민용.

**https://junekinns.github.io/yanbu-dashboard/**

## 네 가지 지표

| 지표 | 데이터 | 읽는 법 |
|---|---|---|
| 관심도 | 영어 위키피디아 `Yanbu`·`Jeddah` 일일 조회수 (Wikimedia Pageviews API) | 최근 60일 중앙값 대비 몇 배. 세상이 갑자기 얀부를 찾아보면 뭔가 일어난 것 |
| 위성 열 감지 | NASA FIRMS VIIRS(S-NPP) 7일 화점 CSV, 서부 사우디 bbox | 24시간 이상 화점 수. 7일 중 4일 이상 같은 3km 격자에서 잡히는 상시 열원(정유 플레어)은 제외. 큰 인프라 화재만 잡히며 위성은 하루 2회 통과 |
| 공지 템포 | 외교부 해외안전여행 사우디 안전공지 (`ntnCd=107`) | 주간 공지 건수 ÷ 평시 중앙값. 대사관이 바빠지면 상황이 급박한 것 |
| 해상 교통 | IMF PortWatch (AIS 집계, ArcGIS FeatureServer) — 얀부 King Fahd 항·제다항 일일 입항, 밥엘만데브 일일 통과 | 최근 7일 합 ÷ 지난 1년 7일 합 중앙값. 유일하게 **낮을수록 위험**. 약 3~5일 지연 |

**공격·요격·경보 로그**: 사우디에는 이스라엘 같은 공개 사이렌 API가 없다. 대신 민방위 경보·연합군 요격 발표가 1~2시간 안에 주요 매체에 보도되는 점을 이용해, 영문·국문 Google News 검색 결과를 허용 매체로 걸러 (현지 날짜·대상 도시·유형[경보/요격/피격/공습])로 묶어 사건별 한 줄로 만든다. 부인·분석·반응 기사는 제외. 후티 측 성명은 SABA 영문판 홈에서 군 대변인 관련 제목 3건을 접이식으로 붙인다(상대측 주장으로 명시).

여기에 외교부 지역별 여행경보 단계(얀부/제다가 어느 단계 지역인지)를 한 줄로, 최근 공지 3건을 요약과 함께 보여준다. 언론 보도는 Google News RSS 검색 결과를 국내·해외 주요 매체 허용목록(연합·KBS·조선·중앙… / Reuters·AP·BBC·Al Jazeera…)으로 걸러 각 5건만 싣는다 — GDELT처럼 키워드로 긁는 게 아니라 매체를 고르는 방식이라 잡음이 적다.

2026년 9월 10일 송유관 피격 당시 세 지표가 모두 반응했다: Yanbu 조회수 130→780/일, 서부 사우디 화점 7→39건/일, 외교부 공지 주 1건→7건.

## 실행

```bash
pip install -r requirements.txt
python3 scripts/fetch_data.py     # data/latest.json 생성 (키·로그인 불필요)
python3 -m http.server 8765       # http://localhost:8765
```

소스가 실패하면 직전 성공 데이터를 유지하고 `stale: true`로 표시한다. 위성 화점의 "평시" 기준선은 실행마다 `data/latest.json`의 `firms.history`에 일별 건수를 쌓아 7일 이상 모이면 계산한다.

## 배포

GitHub Pages(main 루트). `.github/workflows/update.yml`이 6시간마다 스크립트를 실행하고 `data/latest.json`을 커밋한다.

## 시도했지만 버린 것

- ACLED API — 무료(Open) 등급은 API 접근 불가
- 미국무부 여행경보 — Akamai 봇 차단(403)
- UKMTO 해상 속보 — Cloudflare 봇 차단
- GDELT 뉴스 검색 — 키워드 매칭이 느슨해 무관한 기사 다수
- 항공기 추적(OpenSky·adsb.lol) — 사우디 상공 수신기가 거의 없어 데이터 없음
- 한국어 위키 조회수 — 트래픽이 너무 적음
- SPA(사우디 국영통신) — Next.js 렌더링이라 정적 스크래핑 불가
- FAA DINS NOTAM(공역 폐쇄) — Akamai 403
