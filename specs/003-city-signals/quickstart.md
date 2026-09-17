# Quickstart: 도시 단위 재편 검증

## Prerequisites

- `requests` 있는 Python 3.12 (001의 스크래치 venv), Node + Playwright(설치됨).
- FAA 자격증명은 없어도 된다(US6은 비활성 경로만 검증).

## 1. 수집 + 스키마·불변식 (US1·US2·US3·US4·US5)

```bash
python3 scripts/fetch_data.py
python3 - <<'EOF'
import json, datetime as dt
d = json.load(open("data/latest.json"))
# 제거 확인
assert "regions" not in d and "maritime" not in d, "권역/해상 잔존"
assert "regions" not in d["firms"] and "hotspots" in d["firms"]
assert all("region" not in p and "port" not in p for p in d["mofa"]["places"])
# 사건 템포 == 이력 직접 집계
today = dt.date.today()  # 사우디 현지 날짜와 최대 1일 차이 가능 → 스크립트는 AST 기준으로 계산하므로 아래는 events.today 사용
ev = d["events"]; days7 = set(); 
base = dt.date.fromisoformat(ev["today"])
w7 = {(base - dt.timedelta(days=i)).isoformat() for i in range(7)}
p7 = {(base - dt.timedelta(days=i)).isoformat() for i in range(7, 14)}
for city, t in ev["tempo"].items():
    assert t["total7d"] == sum(1 for e in ev["events"] if e["city"] == city and e["date"] in w7), city
    if ev["history_days"] >= 14:
        assert t["prev7d"] is not None and t["prev_total"] == sum(1 for e in ev["events"] if e["city"] == city and e["date"] in p7), city
    else:
        assert t["prev7d"] is None, ("14일 미만인데 비교 표시", city)
# 후티 언급 == 이력 직접 집계
tg = d["telegram"]; since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)).isoformat()
for city, n in tg["mentions7d"].items():
    assert n == sum(1 for m in tg["messages"] if m["iso"] >= since and city in m["places"]), city
# 외교부 변경 이력 필드
assert "changes" in d["mofa"] and "tracking_since" in d["mofa"]
# NOTAM 비활성
assert d["notams"]["ok"] and d["notams"]["enabled"] is False and "items" not in d["notams"]
print("§1 OK  history_days=", ev["history_days"], "events=", len(ev["events"]), "messages=", len(tg["messages"]))
EOF
```

**Expect**: `§1 OK`. (`events.today`는 스크립트가 넣는 사우디 현지 오늘 날짜 — data-model에 추가.)

## 2. 이력 누적·변경 감지 동작 (US2·US4)

```bash
# 2a. 두 번 연속 실행해도 사건·메시지가 중복되지 않는다
python3 scripts/fetch_data.py && python3 -c "import json; d=json.load(open('data/latest.json')); print(len(d['events']['events']), len(d['telegram']['messages']))"
python3 scripts/fetch_data.py && python3 -c "import json; d=json.load(open('data/latest.json')); print(len(d['events']['events']), len(d['telegram']['messages']))"
# 2b. 단계 변경 주입: 이전 값에서 제다 level을 2.5로 바꿔 놓고 실행 → changes에 제다 항목
python3 - <<'EOF'
import json; p="data/latest.json"; d=json.load(open(p))
for x in d["mofa"]["places"]:
    if x["name"]=="얀부": x["level"]=2.5; x["level_name"]="특별여행주의보"
json.dump(d, open(p,"w"), ensure_ascii=False, indent=1)
EOF
python3 scripts/fetch_data.py && python3 -c "import json; d=json.load(open('data/latest.json')); print([c for c in d['mofa']['changes'] if c['city']=='얀부'][:1])"
# 2c. 외교부 실패 실행에서는 가짜 변경이 생기지 않는다
python3 - <<'EOF'
import sys; sys.path.insert(0,"scripts"); import fetch_data as f
f.MOFA_COUNTRY_URL="https://invalid.invalid/x"; n0=len(f.load_previous()["mofa"]["changes"]); f.main()
print("changes unchanged:", len(f.load_previous()["mofa"]["changes"])==n0)
EOF
python3 scripts/fetch_data.py   # 원복
```

**Expect**: 2a 두 줄의 숫자가 같거나 두 번째가 크다(중복 없음). 2b에 `{'city': '얀부', 'from': 2.5, 'to': 3, ...}`. 2c `True`. (2b가 만든 인위적 변경 1건은 커밋 전에 `changes`에서 제거한다.)

## 3. 화면 (US1·US3·US5) — Playwright

```bash
python3 -m http.server 8123 &
node - <<'EOF'
import("playwright").then(async ({ chromium }) => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 2400 } });
  const errors = []; p.on("pageerror", e => errors.push(String(e)));
  await p.goto("http://localhost:8123/index.html", { waitUntil: "networkidle" });
  await p.waitForSelector("#city-table tbody tr");
  const text = await p.evaluate(() => document.body.innerText);
  for (const bad of ["GitHub 로그인", "해상 교통", "공지 템포", "권역"]) if (text.includes(bad)) console.log("LEFTOVER:", bad);
  const rows = await p.$$eval("#city-table tbody tr", trs => trs.map(tr => tr.innerText.replace(/\s+/g, " ").trim()));
  console.log("rows:", rows.length, rows.slice(0, 4));
  console.log("headline:", await p.$eval("#headline", e => e.innerText));
  console.log("mentions:", await p.$eval("#tg-mentions", e => e.innerText));
  console.log("legend has hotspots:", /위성 이상 화점/.test(text), "notam section:", !!(await p.$("#notam")));
  await p.click("#city-table tbody tr:first-child td:first-child");
  await p.waitForTimeout(800);
  console.log("popup open:", !!(await p.$(".leaflet-popup")));
  await p.setViewportSize({ width: 390, height: 844 }); await p.waitForTimeout(300);
  console.log("mobile overflow:", await p.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth));
  await p.screenshot({ path: "city-mobile.png", fullPage: true });
  console.log("errors:", errors); await b.close();
});
EOF
```

**Expect**: `LEFTOVER` 없음, rows ≥ 15이고 첫 줄이 3단계 도시, headline에 "출국권고"·"최근"·"공지" 문장, mentions에 "검증되지 않음", 화점 범례 true, notam section false, popup open true, mobile overflow false, errors [].

## 4. 시드 + 배포

```bash
EVENT_DAYS=14 python3 scripts/fetch_data.py   # 1회. 국문 쪽 이력이 ~9일 채워짐(research.md §1)
git add -A && git commit && git pull --rebase -X theirs origin main && git push
gh workflow run update.yml && gh run watch $(gh run list --workflow=update.yml --limit 1 --json databaseId -q '.[0].databaseId') --exit-status
```

**Expect**: Actions 로그에 `notams: ok=True`(비활성)와 나머지 소스 ok, 총 30초 이내. Pages에서 §3 반복.

## 5. (키 수령 후) NOTAM 활성 확인

```bash
gh secret set FAA_CLIENT_ID -R junekinns/yanbu-dashboard
gh secret set FAA_CLIENT_SECRET -R junekinns/yanbu-dashboard
gh workflow run update.yml
```

**Expect**: 로그 `notams: ok=True`, 데이터 `notams.enabled: true`, 페이지에 NOTAM 카드. 첫 응답으로 필드 경로(research.md §5)를 확정하고 필요하면 파서를 고친다.
