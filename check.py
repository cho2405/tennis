"""
김포시체육회 파르코스 테니스장 코트 현황 조회
http://www.gimposports.or.kr/bbs/orderCourse.php

사용법:
  python check.py              # 기본 (config.py 설정)
  python check.py 20260709     # 특정 날짜 하루만
  python check.py 20260709 A관 # 날짜 + 코트 지정
"""

import sys
import re
import requests
from datetime import datetime

import config


SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Referer": f"{config.BASE_URL}/bbs/orderCourse.php",
    "Content-Type": "application/x-www-form-urlencoded",
})


def fetch_slots(date: str, room: str, time_unit: int = 1) -> list[dict]:
    """
    timeBoard4.php를 호출해 특정 날짜·코트의 시간 슬롯 반환.

    반환 형식:
      [{"time": "06:00", "available": True/False}, ...]
    """
    year = date[:4]
    month = date[4:6]

    resp = SESSION.post(
        f"{config.BASE_URL}/skin/orders/timeBoard4.php",
        data={
            "toYear": year,
            "toMonth": month,
            "sTeb": config.S_TEB,
            "sRoom": room,
            "orderDate": date,
            "settingTimeSet": str(time_unit),
        },
        timeout=10,
    )
    resp.raise_for_status()
    html = resp.text

    # <label class="on|no labelDate" data="HH:MM" ...>
    pattern = re.compile(r'<label\s+class="([^"]+)"\s+data="(\d{2}:\d{2})"')
    slots = []
    for cls, time_str in pattern.findall(html):
        classes = cls.split()
        if "labelDate" not in classes:
            continue
        available = "no" not in classes   # "on" = 예약 가능, "no" = 불가
        slots.append({"time": time_str, "available": available})

    return slots


def print_court_status(date: str, courts: dict, time_unit: int, target_times: list):
    """날짜별 코트 현황을 표 형태로 출력."""
    date_fmt = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    print(f"\n{'='*60}")
    print(f"  날짜: {date_fmt}  (시간 단위: {time_unit}시간)")
    print(f"{'='*60}")

    all_times = set()
    court_data = {}

    for room, name in courts.items():
        try:
            slots = fetch_slots(date, room, time_unit)
        except Exception as e:
            print(f"  [{name}] 조회 실패: {e}")
            court_data[room] = {}
            continue
        court_data[room] = {s["time"]: s["available"] for s in slots}
        all_times.update(court_data[room].keys())

    if not all_times:
        print("  슬롯 데이터 없음")
        return

    times = sorted(all_times)
    if target_times:
        times = [t for t in times if t in target_times]

    # 헤더
    header_courts = list(courts.items())
    col_w = 6
    time_w = 7
    header = f"{'시간':^{time_w}}" + "".join(f"{name:^{col_w}}" for _, name in header_courts)
    print(header)
    print("-" * (time_w + col_w * len(header_courts)))

    # 행
    for t in times:
        row = f"{t:^{time_w}}"
        for room, name in header_courts:
            avail = court_data.get(room, {}).get(t)
            if avail is None:
                mark = " - "
            elif avail:
                mark = " O "
            else:
                mark = " X "
            row += f"{mark:^{col_w}}"
        print(row)


def main():
    # CLI 인수 처리
    dates = config.TARGET_DATES
    courts = {k: v for k, v in config.COURTS.items()
              if not config.TARGET_COURTS or k in config.TARGET_COURTS}
    time_unit = config.TIME_UNIT
    target_times = config.TARGET_TIMES

    if len(sys.argv) >= 2:
        dates = [sys.argv[1]]
    if len(sys.argv) >= 3:
        room_arg = sys.argv[2]
        courts = {room_arg: config.COURTS.get(room_arg, room_arg)}

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 김포 파르코스 테니스장 코트 현황 조회")
    print(f"  코트: {', '.join(courts.values())}  |  시간단위: {time_unit}h")

    for date in dates:
        print_court_status(date, courts, time_unit, target_times)

    print()


if __name__ == "__main__":
    main()
