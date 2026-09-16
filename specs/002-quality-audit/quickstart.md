# Quickstart: 품질 감사 검증

## Prerequisites

- Python 3.12 + `requests` (로컬에 venv가 없으면 001에서 만든 스크래치 venv 재사용 가능)
- Node + Playwright(`npx playwright` — 001 검증에서 이미 설치됨)

## 1. 정확성 불변식 (US1)

```bash
python3 scripts/fetch_data.py
python3 - <<'EOF'
import json, datetime as dt
d = json.load(open("data/latest.json"))
now = dt.datetime.now(dt.timezone.utc)
def ts(h): return dt.datetime.strptime(f"{h['date']} {h['time'].zfill(4)}", "%Y-%m-%d %H%M").replace(tzinfo=dt.timezone.utc)

# FR-001: last24h는 진짜 24시간
for k, r in d["firms"]["regions"].items():
    within = sum(1 for h in r["hotspots"] if ts(h) >= now - dt.timedelta(hours=24))
    assert r["last24h"] <= within, (k, r["last24h"], within)
    # FR-002: 평시 하한 — 평시가 있고(수집 완료) 값이 6건 이상이면 평시가 0이어도 '평시'일 수 없다
    if r["baseline"] is not None and r["last24h"] >= 6: assert r["tier"] != "평시", (k, r)
    if r["baseline"] is None: assert r["tier"] == "평시", (k, r)  # 수집 중엔 판단하지 않는다

# FR-002 공지 템포
m = d["mofa"]
if m["last7d"] >= 3: assert m["tier"] != "평시", m["tier"]

# FR-007: stale이면 last_ok_at 필수
for k in ("firms","mofa","news","events","telegram","maritime","flights"):
    s = d[k]
    if s.get("stale"): assert s.get("last_ok_at"), k
    if s.get("ok"): assert s.get("last_ok_at") == s.get("fetched_at"), k

# FR-005: flights 평시는 같은 시각 표본
f = d["flights"]
if f.get("baseline") is not None: assert f.get("baseline_n", 0) >= 3
print("OK")
EOF
```

**Expect**: `OK`. (FR-004 72시간 필터는 프론트 검증 3번에서.)

## 2. 견고성 (US2)

### 2a. 소스 하나 고의 파괴 → 나머지 생존

```bash
python3 - <<'EOF'
import sys; sys.path.insert(0, "scripts")
import fetch_data as f
f.MOFA_COUNTRY_URL = "https://invalid.invalid/x"   # DNS 실패 유도
f.PORTWATCH_BASE = "https://invalid.invalid"        # 두 개 동시에
sys.exit(f.main())
EOF
echo "exit=$?"
python3 -c "
import json; d=json.load(open('data/latest.json'))
print({k:(d[k]['ok'], d[k].get('stale'), bool(d[k].get('last_ok_at'))) for k in ('firms','mofa','news','events','telegram','maritime','flights')})"
```

**Expect**: `exit=0`. `mofa`/`maritime`는 `(False, True, True)`, 나머지는 `(True, None|False, True)`. 직후 정상 실행으로 원복:

```bash
python3 scripts/fetch_data.py
```

### 2b. 예상 밖 예외에도 죽지 않음

```bash
python3 - <<'EOF'
import sys; sys.path.insert(0, "scripts")
import fetch_data as f
f.feed_items = lambda xml, allowed: (_ for _ in ()).throw(AttributeError("simulated"))
sys.exit(f.main())
EOF
echo "exit=$?"
python3 -c "import json; d=json.load(open('data/latest.json')); print(d['events']['ok'], d['events']['stale'], d['events']['error'])"
```

**Expect**: `exit=0`, `False True AttributeError: simulated`. 원복 실행 후 진행.

### 2c. 번역 캐시

```bash
python3 - <<'EOF'
import sys; sys.path.insert(0, "scripts")
import fetch_data as f
calls = []
orig = f.translate_ar_ko
f.translate_ar_ko = lambda t: (calls.append(t), orig(t))[1]
f.main()
print("translate calls on 2nd run:", len(calls))
EOF
```

**Expect**: 직전 실행과 메시지 세트가 같으면 `0`.

### 2d. 워크플로우

```bash
grep -n "pull --rebase\|timeout-minutes" .github/workflows/update.yml
```

**Expect**: 두 줄 모두 존재. push 후 Actions에서 1회 실행이 녹색.

## 3. 명확성 (US3) — 헤드리스 브라우저

```bash
python3 -m http.server 8123 &
cd "$SCRATCH" && node - <<'EOF'
import("playwright").then(async ({ chromium }) => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 2400 } });
  const errors = []; p.on("pageerror", e => errors.push(String(e)));
  await p.goto("http://localhost:8123/index.html", { waitUntil: "networkidle" });
  await p.waitForSelector("#event-log li");
  const text = await p.evaluate(() => document.body.innerText);
  for (const bad of ["선택한 권역", "이 세 지표", "HTTPSConnectionPool", "Traceback", "Error("]) if (text.includes(bad)) console.log("STALE COPY:", bad);
  if (!/사우디 현지/.test(text)) console.log("MISSING TZ LABEL");
  const ages = await p.$$eval("#event-log li .ev-time", els => els.map(e => e.textContent));
  console.log("event times:", ages);
  const restCount = (text.match(/그 외 전 지역/g) || []).length; console.log("rest-level lines:", restCount);
  await p.screenshot({ path: "quality-full.png", fullPage: true });
  console.log("pageerrors:", errors); await b.close();
});
EOF
```

**Expect**: `STALE COPY` 없음, `MISSING TZ LABEL` 없음, `event times`가 모두 72시간 이내, `rest-level lines: 1`, `pageerrors: []`. 스크린샷에서 지도 초기 뷰에 지잔·나즈란 마커가 보이고, 중부 해상 교통 타일 제목에 "호르무즈(전국)"이 있다.

stale 표시는 2a의 파괴 실행 직후 페이지를 열어 확인: 타일에 "(N시간 전 값)"이 보이고, 실패 소스 타일 본문에 파이썬 예외가 없다.

## 4. 문서 (US4)

```bash
grep -n "선택 권역\|세 가지 지표\|FlightRadar24" README.md
```

**Expect**: "선택 권역", "세 가지 지표" 없음. FlightRadar24는 "실험 중" 섹션에만.

## 5. 배포

```bash
git pull --rebase && git push
```

Actions 1회 성공 → Pages에서 3번 검사 반복.

## Reference

- 결함 근거: [research.md](./research.md)
- 스키마 변경: [data-model.md](./data-model.md)
