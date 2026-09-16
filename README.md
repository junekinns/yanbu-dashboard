# 얀부·제다 상황판

외교부 해외안전여행(0404.go.kr)의 사우디아라비아 데이터를 6시간마다 자동 수집해, 얀부·제다가 현재 어느 여행경보 단계 지역인지와 최근 안전공지를 한 화면에 보여주는 비공식 정적 대시보드입니다. 사우디에 계신 한인 교민용.

## 무엇을 보여주나

- 얀부·제다 각각의 외교부 여행경보 단계 (지역별 지정을 파싱)
- 두 지역을 외교부 팔레트로 색칠한 지도
- 외교부 사우디 안전공지 최근 8건 + 본문 첫 줄 요약
- 주간 안전공지 건수 (최근 8주) — 공지가 잦아지면 상황이 급박하다는 신호
- 보조 신호로 영국 FCDO 경보 한 줄

## 실행

```bash
pip install -r requirements.txt
python3 scripts/fetch_data.py      # data/latest.json 생성
python3 -m http.server 8765        # http://localhost:8765
```

API 키나 로그인은 필요 없습니다. 소스가 일시적으로 실패하면 스크립트는 직전 성공 데이터를 유지하고 `stale: true`로 표시합니다.

## 배포

GitHub Pages(main 브랜치 루트)로 서빙하고, `.github/workflows/update.yml`이 6시간마다 `scripts/fetch_data.py`를 실행해 `data/latest.json`을 커밋합니다.

## 쓰지 않은 것들 (기록용)

- **ACLED API**: 무료(Open) 등급은 API 접근 불가. Research 등급 승인 필요.
- **미국무부 여행경보**: Akamai 봇 차단으로 로컬·GitHub Actions 모두 403.
- **UKMTO**: Cloudflare 봇 차단.
- **GDELT 뉴스 검색**: 접근은 되지만 키워드 매칭이 느슨해 무관한 기사가 많이 섞임. 외교부 공지가 훨씬 정확해 제거.
