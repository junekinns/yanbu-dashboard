# Implementation Plan: 신호 전수조사 · 지도 고도화 · 수동 갱신

**Branch**: `001-signal-audit` (main 직접 반영) | **Date**: 2026-09-16 | **Spec**: ./spec.md

## Summary

기존 4개 지표 중 근거가 약한 것을 정리하고, 실제로 새로운 무료 소스를 조사해 유의미한 신호만 추가한다. 후티 채널은 한글 번역을 기본 노출로 바꾼다. 지도는 실현 가능한 범위에서 고도화하고, 불가능한 항목은 조사 근거와 함께 README에 기록한다. 수동 갱신은 정적 사이트 제약 안에서 두 갈래(로그인 사용자용 워크플로우 링크 + 방문자용 캐시 무효화 새로고침)로 제공한다.

## Technical Context

**Language/Version**: Python 3.12(수집), 바닐라 JS + Leaflet + Chart.js(프론트)

**Primary Dependencies**: requests(Python), Leaflet.js, Chart.js — 새 패키지 추가 없이 기존 스택 유지

**Storage**: `data/latest.json` 단일 파일 (기존 패턴 유지)

**Testing**: 로컬 `python3 scripts/fetch_data.py` 실행 후 실제 값 검증 + `node -e`로 app.js 구문 검사 + `python3 -m http.server`로 정적 서빙 확인 + GitHub Actions 실행 로그 확인 (기존 프로젝트의 기존 검증 방식, 자동화된 테스트 스위트는 없음)

**Target Platform**: GitHub Pages(정적) + GitHub Actions(6시간 cron)

**Project Type**: 단일 정적 웹사이트 + 데이터 수집 스크립트

**Constraints**: 무료·무키만 사용. 오버엔지니어링 금지(사용자 반복 지시). GitHub Actions 무료 티어 실행 시간.

**Scale/Scope**: 개인/가족 단위 사용자, 트래픽 매우 낮음.

## 조사 대상 (User Story 1, 4)

새 신호 후보와 지도 고도화 후보를 실제 요청으로 검증한다. 결과는 spec.md Assumptions/README "시도했지만 버린 것"에 기록.

## 정리 대상 (User Story 2)

기존 지표별 재검토:
- 위성 열 감지: 유지(피격 화재는 명확한 선행 신호, 앞서 실증됨)
- 공지 템포: 유지하되, 이미 발생한 사건에 대한 정부의 "사후" 대응이라 선행성이 약함을 인지 — 격 낮추거나 보조 지표로
- 해상 교통: 유지(3~5일 지연이지만 유일하게 검증된 하드 데이터)
- (제거됨) 관심도: 이미 제거 완료

## 작업 순서

1. 신규 소스 조사 (병렬 curl 테스트)
2. 지도 고도화 조사
3. 채택 소스를 fetch_data.py에 통합, 기각 소스는 README에 기록
4. 후티 채널 번역 파이프라인 추가
5. 지도/UI 반영
6. 수동 갱신 두 갈래 구현
7. 로컬 검증 → 커밋 → push → Actions 확인 → Pages 확인
