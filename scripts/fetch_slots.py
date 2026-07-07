"""
김포 파르코스 테니스장 코트 현황 수집기
GitHub Actions에서 실행 → data/YYYYMMDD.json 저장
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import http.cookiejar
from datetime import datetime, timedelta

BASE_URL = "http://www.gimposports.or.kr"
S_TEB    = "g"
COURTS   = {
    "A관": "1코트", "B관": "2코트", "C관": "3코트", "D관": "4코트",
    "E관": "5코트", "F관": "6코트", "G관": "7코트", "H관": "8코트",
}

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Connection":      "keep-alive",
    "Referer":         f"{BASE_URL}/bbs/orderCourse.php",
}

# 쿠키 공유 세션
_cookie_jar = http.cookiejar.CookieJar()
_opener     = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cookie_jar))


def _warmup():
    """메인 페이지 GET → 쿠키·세션 획득"""
    req = urllib.request.Request(f"{BASE_URL}/bbs/orderCourse.php", headers=HEADERS)
    try:
        with _opener.open(req, timeout=15) as r:
            r.read()
        print("  [세션 초기화 완료]")
    except Exception as e:
        print(f"  [세션 초기화 경고] {e}", file=sys.stderr)


def fetch_slots(date: str, room: str, unit: int = 1) -> list:
    body = urllib.parse.urlencode({
        "toYear": date[:4], "toMonth": date[4:6], "sTeb": S_TEB,
        "sRoom": room, "orderDate": date, "settingTimeSet": str(unit),
    }).encode()

    headers = {**HEADERS,
               "Content-Type": "application/x-www-form-urlencoded",
               "X-Requested-With": "XMLHttpRequest"}

    req = urllib.request.Request(
        f"{BASE_URL}/skin/orders/timeBoard4.php",
        data=body, method="POST", headers=headers,
    )
    with _opener.open(req, timeout=15) as r:
        html = r.read().decode("utf-8", errors="replace")

    pat = re.compile(r'<label\s+class="([^"]+)"\s+data="(\d{2}:\d{2})"')
    return [
        {"time": t, "available": "no" not in c.split()}
        for c, t in pat.findall(html)
        if "labelDate" in c.split()
    ]


def fetch_date(date: str) -> dict:
    result = {}
    for room, name in COURTS.items():
        try:
            slots = fetch_slots(date, room, unit=1)
            result[room] = {"name": name, "slots": slots}
        except Exception as e:
            print(f"  [{name}] 오류: {e}", file=sys.stderr)
            result[room] = {"name": name, "slots": [], "error": str(e)}
        time.sleep(0.3)   # 요청 간 딜레이
    return result


def main():
    today = datetime.now()

    # 이번 달 말일 계산
    if today.month == 12:
        last_day = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last_day = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

    # 오늘부터 말일까지
    days_left = (last_day - today).days + 1
    dates = [
        (today + timedelta(days=i)).strftime("%Y%m%d")
        for i in range(days_left)
    ]
    print(f"수집 대상: {dates[0]} ~ {dates[-1]} ({len(dates)}일)")

    # 세션 웜업 (쿠키 획득)
    _warmup()
    time.sleep(1)

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(data_dir, exist_ok=True)

    for date in dates:
        print(f"수집 중: {date}")
        data = fetch_date(date)
        path = os.path.join(data_dir, f"{date}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        print(f"  저장: {path}")
        time.sleep(0.5)

    # summary per date
    summary = {}
    for date in dates:
        path = os.path.join(data_dir, f"{date}.json")
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            total = avail = 0
            for rd in d.values():
                for slot in rd.get("slots", []):
                    total += 1
                    if slot.get("available"):
                        avail += 1
            summary[date] = {"avail": avail, "total": total}
        except Exception:
            summary[date] = {"avail": 0, "total": 0}

    meta = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S (KST)"),
        "dates":   dates,
        "summary": summary,
    }
    with open(os.path.join(data_dir, "meta.json"), "w") as f:
        json.dump(meta, f)

    print("완료")


if __name__ == "__main__":
    main()
