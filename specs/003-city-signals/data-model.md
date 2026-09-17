# Data Model: `data/latest.json` (재편 후)

002까지의 스키마에서 **제거되는 것**: `regions`, `maritime`, `firms.regions`(일별·평시·타일), `mofa.weekly_counts`, `mofa.tier` 배지 용도, places의 `region`·`port`. 공통 필드(`ok`, `error`, `fetched_at`, `last_ok_at`, `stale`)는 그대로.

## `mofa`

| Field | 설명 |
|---|---|
| `places[]` | `{name, lat, lon, level, level_name}` — 좌표 있는 지점만 |
| `changes[]` | **신규** `{city, from, from_name, to, to_name, at}` — 단계 변경 이력, `at` 기준 90일 유지, 최신순 |
| `tracking_since` | **신규** 변경 추적 시작 시각(ISO). 최초 실행의 `fetched_at`, 이후 보존 |
| `notices[]` | 상위 3건(변경 없음) |
| `last7d`, `baseline`, `tier` | 헤드라인 문장용(변경 없음). `weekly_counts`는 제거 |
| `advisories[]` | 원문 파싱 결과(변경 없음) |

**규칙**: 변경 감지는 이전·현재 `level`이 모두 숫자일 때만. 수집 실패 실행에서는 비교 없음.

## `events`

| Field | 설명 |
|---|---|
| `events[]` | **이력 전체**(30일, 최신순). 항목 `{date, time, iso, city, type, lat, lon, title, url, source, outlets}` — 키는 `date|city|type` |
| `tempo` | **신규** `{city: {"7d": {"경보": n, "요격": n, "피격": n, "공습": n}, "total7d": n, "prev7d": {...} \| null, "prev_total": n \| null}}` |
| `history_days` | **신규** `(오늘 − 가장 오래된 date) + 1`, 사우디 현지 날짜 기준 |
| `history_since` | **신규** 가장 오래된 `date` |
| `today` | **신규** 창 계산에 쓴 사우디 현지 오늘 날짜(`YYYY-MM-DD`). 검증 스크립트가 같은 기준으로 재계산할 때 사용 |

**규칙**: 병합 시 `outlets`는 max, `iso/time`은 더 이른 값, `title/url/source`는 기존 유지. `prev7d`/`prev_total`은 `history_days >= 14`일 때만 non-null. 창은 `date`(사우디 현지) 기준: 7d = 오늘 포함 7일, prev7d = 그 앞 7일.

**불변식**: 각 도시의 `tempo[city].total7d == len([e for e in events if e.city == city and e.date in 7d창])`.

## `telegram`

| Field | 설명 |
|---|---|
| `messages[]` | **이력**(14일, 최신순). `{time, iso, places[], text_ar, text_ko \| null, url}` — 키는 `url`. 사우디 언급 필터 통과분만 |
| `mentions7d` | **신규** `{city: n}` 내림차순 — 최근 7일 메시지에서 도시별 (메시지당 1회) 합 |

**불변식**: `mentions7d[city] == len([m for m in messages if m.iso in 7d창 and city in m.places])`.

## `firms`

| Field | 설명 |
|---|---|
| `hotspots[]` | 사우디 박스 안 이상 화점(상시 플레어 제외), 최근 7일, 최대 500건, `{lat, lon, frp, date, time, confidence}` |

`regions`·`daily_counts`·`baseline`·`tier`·`history` 제거.

## `notams` (선택)

| Field | 설명 |
|---|---|
| `enabled` | 비밀값 존재 여부. `false`면 아래 필드 없음, `ok: true` |
| `items[]` | `{location, number, effective_start, effective_end, kind, text}` — 공역 제한·폐쇄 성격만, `text`는 200자 |
| `locations[]` | 조회 대상 ICAO 코드 |

**규칙**: 비활성은 실패가 아니다(`ok: true`, `stale` 없음). 활성 상태의 실패는 다른 소스와 같은 carry_over.

## `flights` (변경 없음)

## `news` (변경 없음)

## 프론트 파생값 (저장 안 함)

- **도시 행 정렬 키**: `(-level, -total7d, name)`.
- **행의 변경 배지**: `changes` 중 해당 도시이고 `at`이 30일 이내인 최신 1건.
- **헤드라인 ①**: `level >= 3` 도시명 나열(정렬 키 순) + `level < 3` 최빈 단계.
- **지도 초기 bounds**: `places` 좌표 합집합.
