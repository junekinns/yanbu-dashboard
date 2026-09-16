# Data Model: 품질 감사 — `data/latest.json` 변경

기존 스키마는 001 `data-model.md`에 있다. 여기는 이번 변경분만.

## 모든 Source Result 블록 공통

| Field | 변경 | 설명 |
|---|---|---|
| `last_ok_at` | **신규** | 마지막으로 `ok: true`였던 실행의 `fetched_at`. 성공 시 갱신, stale carry-over 시 보존. 프론트 `staleTag`가 경과 시간 계산에 사용 |
| `error` | 형식 변경 | 예상 밖 예외는 `"TypeName: message"` 형식(가드에서 생성). 기존 예상 예외는 그대로 |

**불변식**: `stale == true` 이면 `last_ok_at != null` (이전 성공값이 있어야 stale이 가능하므로).

## `firms.regions[key]`

| Field | 변경 | 설명 |
|---|---|---|
| `last24h` | 의미 변경 | 현재 시각 기준 지난 24시간(UTC, `acq_date`+`acq_time`) 이상 화점 수. 이전: 어제 00:00 UTC 이후 |
| `flares24h` | 의미 변경 | 같은 창의 상시 열원 수 |
| `tier` | 계산 변경 | `tier_up(ratio(last24h, max(baseline, 2)))`. `baseline` 필드 자체는 실제 중앙값 |
| `daily_counts`, `history`, `baseline`, `hotspots` | 변경 없음 | |

**불변식**: `last24h <= len([h for h in hotspots if ts(h) >= now-24h])` (hotspots는 300건 캡이 있어 등호가 아닐 수 있음).

## `mofa`

| Field | 변경 | 설명 |
|---|---|---|
| `tier` | 계산 변경 | `tier_up(ratio(last7d, max(baseline, 1)), labels=("급증","증가","평시"))` |
| `notices` | 소스 변경 | `pageSize=100`으로 수집(저장은 여전히 상위 3건). `weekly_counts` 계산이 100건을 본다 |

## `telegram.messages[]`

스키마 변경 없음. 동작 변경: `text_ko`는 `previous.messages` 중 `url`이 같고 `text_ar`의 해시가 같은 항목이 있으면 그 값을 재사용한다. 해시는 저장하지 않고 실행 시 계산한다(`text_ar`이 이미 저장되어 있으므로).

## `flights`

| Field | 변경 | 설명 |
|---|---|---|
| `history` | cap 변경 | `{"YYYY-MM-DDTHH": count}` 최근 336개(14일×24) |
| `baseline` | 의미 변경 | 현재와 같은 `HH`를 가진 과거 항목 값의 중앙값. 3개 미만이면 `null` |
| `baseline_n` | **신규** | 평시 계산에 쓰인 같은-시각 표본 수. 프론트가 "수집 중 (n/3)" 표시에 사용 |

## `events`

스키마 변경 없음. 프론트가 `iso >= now-72h`로 목록을 거른다(지도는 이미 `state.hours`로 거름).

## 프론트 파생값 (저장 안 함)

- **stale 경과**: `Math.round((Date.now() - Date.parse(src.last_ok_at)) / 3600e3)` 시간; 48시간 이상이면 일 단위.
- **경보 한 줄 기본 단계**: `mofa.places` 중 `level < 3`인 항목의 `level` 최빈값 하나.
- **지도 초기 bounds**: `regions[].box` ∪ `mofa.places[].(lat, lon)`.
