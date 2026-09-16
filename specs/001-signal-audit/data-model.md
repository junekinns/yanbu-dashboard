# Data Model: 신호 전수조사 · 지도 고도화 · 수동 갱신

소스는 `data/latest.json` (fetch_data.py가 생성, GitHub Actions가 6시간마다 갱신 또는 수동 트리거). 프론트(app.js)는 이 파일을 그대로 소비한다. 새 필드는 없다 — 기존 스키마 위에서 렌더링 방식만 바꾼다.

## Region

권역 메타데이터. 지표 타일 그리드와 지도 통합 뷰의 기준이 되는 엔티티.

| Field | Type | Description |
|---|---|---|
| `key` | string | `west` \| `central` \| `east` |
| `name` | string | 표시명 (서부/중부/동부) |
| `label` | string | 부제 (예: "얀부 · 제다") |
| `primary_port` | string \| null | `maritime.series`의 항구 키 |
| `chokepoint` | string | `maritime.series`의 해협 키 (primary_port 없을 때 대체) |
| `center` | [lat, lon] | 개별 권역 지도 중심 (기존 탭 방식에서 사용, 통합 뷰에서는 미사용) |
| `zoom` | number | 개별 권역 줌 레벨 (통합 뷰에서는 미사용) |
| `box` | [south, north, west, east] | 권역 bounding box — **통합 뷰의 지도 bounds 계산에 사용** |

**통합 뷰 규칙**: 지도는 `regions[].box`를 모두 포함하는 `L.latLngBounds`로 `fitBounds()`한다. 권역별 `center`/`zoom`은 더 이상 지도 뷰 전환에 쓰이지 않는다(개별 포커스가 필요 없어졌으므로).

## Signal Source (기존, 변경 없음)

- **Firms** (`firms.regions[key]`): `tier`, `last24h`, `baseline`, `flares24h`, `daily_counts[]`, `hotspots[]`. 권역별 독립값 → 통합 뷰에서는 **세 권역 모두** 타일로 렌더링(기존엔 선택된 1개만).
- **Mofa** (`mofa`): 전국 단일값(`tier`, `last7d`, `baseline`, `weekly_counts[]`) + `places[]`(도시별 `region`, `level`). 지표 타일은 전국 카드 1개 유지. `places[]`는 권역 필터 없이 전체 표시하되 각 항목에 `region` 배지 추가.
- **Maritime** (`maritime.series[portKey]`): `tier`, `last7`, `baseline7`, `spark[]`. `region.primary_port ?? region.chokepoint`로 권역별 항구를 찾아 → 통합 뷰에서는 세 권역 모두 타일로 렌더링.

## Event (기존, 변경 없음 — 소비 방식만 변경)

`events.events[]`: `region`, `city`, `lat/lon`, `type`, `date/time/iso`, `title`, `url`, `source`, `outlets`.

**통합 뷰 규칙**: 목록/지도 모두 권역 필터를 적용하지 않고 전체를 그린다(기존에도 필터링 없이 `.local` 강조만 했으므로 목록 로직 변화는 작음). 각 `<li>`에 `e.region` 기준 배지(서부/중부/동부)를 추가해 소속을 표시.

## Telegram Message (기존, 변경 없음 — 소비 방식만 변경)

`telegram.messages[]`: `time`, `text_ko`, `text_ar`, `places[]`, `url`.

**통합 뷰 규칙**: `places[]`를 `mofa.places[].name → region` 매핑으로 역참조해 메시지에 권역 배지를 붙인다(현재는 "지금 선택된 권역 도시가 언급되면 강조"만 하던 로직을 "언급된 각 도시의 권역을 배지로 표시"로 대체).

## UI State (변경)

- **제거**: `state.region`, `localStorage["region"]`, `currentRegion()`.
- **유지**: `state.hours`(지도 기간 필터), `state.base`(바탕지도), `state.map/layer/baseLayers/charts`.
