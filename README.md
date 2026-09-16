# 얀부·제다 상황판

사우디아라비아 얀부·제다 지역의 공개된 간접 신호(GDELT 실시간 뉴스 언급량, 미국무부 여행경보)와, 자동 수집이 어려운 전문 소스(ACLED, UKMTO, 대한민국 외교부/대사관 등)로의 바로가기 링크를 모아 보여주는 비공식 정적 대시보드입니다.

## 로컬에서 미리보기

```bash
python3 -m http.server 8765
```

`http://localhost:8765` 접속.

## 실제 데이터로 채우기

API 키나 로그인 없이 바로 실행할 수 있습니다.

```bash
pip install -r requirements.txt
python3 scripts/fetch_data.py
```

`data/latest.json`이 실제 데이터로 갱신됩니다.

- **GDELT** (실시간 뉴스 언급량): 무료, 키 불필요. 다만 짧은 시간에 요청을 많이 보내면 429(rate limit)가 뜰 수 있음 — 스크립트가 자동 재시도함.
- **미국무부 여행경보**: 공식 API/RSS가 없어 페이지를 직접 파싱합니다. 사이트 구조가 바뀌거나 봇 차단에 걸리면 실패할 수 있습니다.

두 소스 모두 실패해도 스크립트는 죽지 않고 직전 성공 데이터를 그대로 유지합니다(`"stale": true`로 표시).

### 왜 ACLED API를 직접 쓰지 않나요?

ACLED는 2025년경 API 인증을 이메일/비밀번호 기반 OAuth로 전환했는데, 무료 "Open" 등급 계정은 API 접근 자체가 막혀 있고 구조화된 사건 데이터를 받으려면 "Research" 등급 승인이 필요합니다(개인 프로젝트로는 사실상 어려움). 대신 ACLED가 직접 운영하는 [Yemen Conflict Monitor](https://acleddata.com/monitor/yemen-conflict-monitor)(홍해 공격 전용 지도 포함, 주간 갱신)를 바로가기 링크로 제공합니다.

### 왜 지도에 사건 마커가 없나요?

무료로 안정적인 위경도 기반 사건 데이터를 구할 방법을 찾지 못했습니다(ACLED는 위 이유로 제한, GDELT GEO API는 테스트 시점에 응답하지 않음, UKMTO는 Cloudflare 차단). 대신 얀부/제다 위치만 지도에 표시하고, 실제 사건 지도는 ACLED/UKMTO 원본 링크로 안내합니다.

## GitHub Pages로 배포하기

1. github.com에 새 저장소를 만들고 이 폴더를 push합니다.
2. Settings → Pages 에서 배포 브랜치를 main, 폴더를 `/ (root)`로 설정합니다.
3. `.github/workflows/update.yml`이 6시간마다 자동으로 `scripts/fetch_data.py`를 실행하고 `data/latest.json`을 커밋합니다. Actions 탭에서 수동 실행(workflow_dispatch)도 가능합니다.

## 주의

비공식 개인 프로젝트입니다. 응급 상황에는 반드시 현지 대사관/영사관의 공식 공지를 확인하세요. 뉴스 언급량(GDELT)은 검증되지 않은 자동 수집 데이터이므로, 동일 헤드라인이 낯선 도메인 여러 곳에 동시에 올라오는 등 출처 신뢰도를 직접 판단해야 합니다.
