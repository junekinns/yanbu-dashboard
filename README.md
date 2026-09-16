# 얀부 지수

US Pizza Index처럼, 공식 발표가 말하지 않는 것을 간접 신호로 읽는 비공식 대시보드. 사우디아라비아 얀부·제다에 있는 한인 교민용.

**https://junekinns.github.io/yanbu-dashboard/**

## 세 가지 지표

| 지표 | 데이터 | 읽는 법 |
|---|---|---|
| 관심도 | 영어 위키피디아 `Yanbu`·`Jeddah` 일일 조회수 (Wikimedia Pageviews API) | 최근 60일 중앙값 대비 몇 배. 세상이 갑자기 얀부를 찾아보면 뭔가 일어난 것 |
| 위성 열 감지 | NASA FIRMS VIIRS(S-NPP) 7일 화점 CSV, 서부 사우디 bbox | 24시간 화점 수. 공습·폭발 화재가 위성에 그대로 찍힘. 지도에 FRP 크기로 표시 |
| 공지 템포 | 외교부 해외안전여행 사우디 안전공지 (`ntnCd=107`) | 주간 공지 건수 ÷ 평시 중앙값. 대사관이 바빠지면 상황이 급박한 것 |

여기에 외교부 지역별 여행경보 단계(얀부/제다가 어느 단계 지역인지)를 한 줄로, 최근 공지 3건을 요약과 함께 보여준다.

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
