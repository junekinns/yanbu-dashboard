# 얀부·제다 상황판

사우디아라비아 얀부·제다 지역의 공개된 간접 신호(ACLED 분쟁 이벤트, UKMTO 해상 보안 속보, 미국무부 여행경보)를 모아 보여주는 비공식 정적 대시보드입니다.

## 로컬에서 미리보기

```bash
python3 -m http.server 8765
```

`http://localhost:8765` 접속. `data/latest.json`은 샘플 데이터가 미리 들어있습니다.

## 실제 데이터로 채우기

1. https://acleddata.com 에서 무료 계정을 만들고 API 키를 발급받습니다.
2. 로컬에서 테스트하려면:
   ```bash
   pip install -r requirements.txt
   ACLED_API_KEY=your_key ACLED_EMAIL=your_email python3 scripts/fetch_data.py
   ```
3. `data/latest.json`이 실제 데이터로 갱신됩니다.

UKMTO(홍해 해상 보안 속보)와 미국무부 여행경보는 공식 API/RSS가 없어 페이지를 직접 파싱합니다. 사이트 구조가 바뀌면 깨질 수 있으며, 특히 UKMTO는 Cloudflare 봇 차단으로 자주 실패할 수 있습니다. 실패 시 스크립트는 죽지 않고 직전 성공 데이터를 그대로 유지합니다(`"stale": true`로 표시).

## GitHub Pages로 배포하기

1. github.com에 새 저장소를 만들고 이 폴더를 push합니다.
2. 저장소 Settings → Secrets and variables → Actions 에서 `ACLED_API_KEY`, `ACLED_EMAIL` 시크릿을 등록합니다.
3. Settings → Pages 에서 배포 브랜치를 main, 폴더를 `/ (root)`로 설정합니다.
4. `.github/workflows/update.yml`이 6시간마다 자동으로 `scripts/fetch_data.py`를 실행하고 `data/latest.json`을 커밋합니다. Actions 탭에서 수동 실행(workflow_dispatch)도 가능합니다.

## 주의

비공식 개인 프로젝트입니다. 응급 상황에는 반드시 현지 대사관/영사관의 공식 공지를 확인하세요.
