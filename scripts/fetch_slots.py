"""
김포 파르코스 테니스장 코트 현황 수집기
GitHub Actions에서 실행 → data/YYYYMMDD.json 저장
"""

import json
import os
import re
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

BASE_URL = "http://www.gimposports.or.kr"
S_TEB    = "g"
COURTS   = {
    "A관": "1코트", "B관": "2코트", "C관": "3코트", "D관": "4코트",
    "E관": "5코트", "F관": "6코트", "G관": "7코트", "H관": "8코트",
}


def fetch_slots(date: str, room: str, unit: int = 1) -> list:
    body = urllib.parse.urlencode({
        "toYear": date[:4], "toMonth": date[4:6], "sTeb": S_TEB,
        "sRoom": room, "orderDate": date, "settingTimeSet": str(unit),
    }).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/skin/orders/timeBoard4.php",
        data=body, method="POST",
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; TennisBot/1.0)",
            "Referer":    f"{BASE_URL}/bbs/orderCourse.php",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
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
    return result


def main():
    today = datetime.now()
    # 오늘부터 14일치 수집
    dates = [
        (today + timedelta(days=i)).strftime("%Y%m%d")
        for i in range(14)
    ]

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(data_dir, exist_ok=True)

    for date in dates:
        print(f"수집 중: {date}")
        data = fetch_date(date)
        path = os.path.join(data_dir, f"{date}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        print(f"  저장: {path}")

    # 최신 업데이트 시각 기록
    meta = {"updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S (KST)")}
    with open(os.path.join(data_dir, "meta.json"), "w") as f:
        json.dump(meta, f)

    print("완료")


if __name__ == "__main__":
    main()
