# 김포 파르코스 테니스장 코트 현황

> **GitHub Pages**: https://cho2405.github.io/tennis

코트 예약 현황을 실시간으로 확인하는 정적 대시보드입니다.

## 동작 방식

```
GitHub Actions (매 시간)
  → gimposports.or.kr 크롤링
  → data/YYYYMMDD.json 저장 & 자동 커밋

GitHub Pages
  → index.html이 data/*.json을 직접 읽어 렌더링
```

## 구조

```
index.html           # 정적 대시보드 (소개 / 코트현황 / 참여현황)
data/
  20260702.json      # 날짜별 코트 슬롯 데이터 (Actions 자동 생성)
  meta.json          # 마지막 갱신 시각
scripts/
  fetch_slots.py     # 크롤러 (Actions에서 실행)
.github/workflows/
  fetch.yml          # 매 시간 자동 실행 워크플로우
```

## GitHub Pages 설정

1. 레포 → Settings → Pages
2. **Source**: `Deploy from a branch`
3. **Branch**: `main` / `/ (root)`
4. 저장 → `https://cho2405.github.io/tennis` 접속

## Actions 수동 실행

GitHub 레포 → Actions → `Fetch Court Status` → `Run workflow`
