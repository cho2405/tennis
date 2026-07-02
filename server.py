"""
김포 테니스 통합 대시보드
  python3 server.py [port=8080]
  → http://localhost:8080
"""

import json, re, sys, os, uuid, hashlib, time
import urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
from http import cookies as http_cookies

import config as cfg


# ═══════════════════════════════════════════════════════════════
#  1. 사용자 데이터 관리 (JSON 파일)
# ═══════════════════════════════════════════════════════════════
DATA_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

def _ensure():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w") as f: json.dump({}, f)

def load_users() -> dict:
    _ensure()
    with open(USERS_FILE, encoding="utf-8") as f: return json.load(f)

def save_users(u: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(u, f, ensure_ascii=False, indent=2)

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════
#  2. 세션 관리 (인메모리)
# ═══════════════════════════════════════════════════════════════
SESSIONS: dict = {}

def new_session(uid: str, name: str, email: str = "") -> str:
    tok = uuid.uuid4().hex
    SESSIONS[tok] = {"uid": uid, "name": name, "email": email,
                     "exp": time.time() + 86400 * 7}
    return tok

def get_session(tok: str):
    if not tok: return None
    s = SESSIONS.get(tok)
    if s and s["exp"] > time.time(): return s
    SESSIONS.pop(tok, None); return None

def del_session(tok: str):
    SESSIONS.pop(tok or "", None)

def session_from_req(handler):
    raw = handler.headers.get("Cookie", "")
    jar = http_cookies.SimpleCookie(raw)
    tok = jar["sid"].value if "sid" in jar else None
    return tok, get_session(tok)


# ═══════════════════════════════════════════════════════════════
#  3. 슬롯 조회
# ═══════════════════════════════════════════════════════════════
def fetch_slots(date: str, room: str, unit: int = 1) -> list:
    body = urllib.parse.urlencode({
        "toYear": date[:4], "toMonth": date[4:6], "sTeb": cfg.S_TEB,
        "sRoom": room, "orderDate": date, "settingTimeSet": str(unit),
    }).encode()
    req = urllib.request.Request(
        f"{cfg.BASE_URL}/skin/orders/timeBoard4.php",
        data=body, method="POST",
        headers={"User-Agent": "Mozilla/5.0",
                 "Referer": f"{cfg.BASE_URL}/bbs/orderCourse.php",
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode("utf-8", errors="replace")
    pat = re.compile(r'<label\s+class="([^"]+)"\s+data="(\d{2}:\d{2})"')
    return [{"time": t, "available": "no" not in c.split()}
            for c, t in pat.findall(html) if "labelDate" in c.split()]

def get_all_slots(date: str, unit: int = 1) -> dict:
    result = {}
    for room, name in cfg.COURTS.items():
        try:
            result[room] = {"name": name, "slots": fetch_slots(date, room, unit)}
        except Exception as e:
            result[room] = {"name": name, "slots": [], "error": str(e)}
    return result


# ═══════════════════════════════════════════════════════════════
#  4. HTML – 공통 레이아웃
# ═══════════════════════════════════════════════════════════════
_COMMON_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;
     background:#f0f4f8;color:#222;min-height:100vh;display:flex;flex-direction:column}
a{text-decoration:none;color:inherit}

/* ── 네비 ── */
.navbar{background:#1c2e4a;position:sticky;top:0;z-index:1000;
        box-shadow:0 2px 8px rgba(0,0,0,.35)}
.nav-inner{max-width:1200px;margin:0 auto;display:flex;align-items:center;
           height:58px;padding:0 20px;gap:6px}
.nav-brand{font-size:1.1rem;font-weight:800;color:#fff;letter-spacing:-.3px;
           margin-right:12px;white-space:nowrap;display:flex;align-items:center;gap:6px}
.nav-brand:hover{color:#5dade2}
.nav-menu{display:flex;align-items:center;gap:2px;flex:1}

.nav-item>a{display:flex;align-items:center;gap:3px;padding:8px 13px;
            color:rgba(255,255,255,.82);border-radius:6px;font-size:.88rem;
            font-weight:500;transition:all .15s;white-space:nowrap}
.nav-item>a:hover{background:rgba(255,255,255,.1);color:#fff}
.nav-item.active>a{background:rgba(93,173,226,.22);color:#5dade2;font-weight:700}
.caret{font-size:.65rem;opacity:.55}

/* 드롭다운 */
.has-dd{position:relative}
.dropdown{display:none;position:absolute;top:calc(100% + 8px);left:0;
          background:#fff;border-radius:8px;
          box-shadow:0 6px 20px rgba(0,0,0,.14);min-width:170px;overflow:hidden;z-index:999}
.dropdown a{display:flex;align-items:center;gap:8px;padding:11px 16px;
            color:#333;font-size:.86rem;border-bottom:1px solid #f0f0f0;transition:background .12s}
.dropdown a:last-child{border-bottom:none}
.dropdown a:hover{background:#eaf4fd;color:#1a5276}
.has-dd:hover .dropdown,.has-dd:focus-within .dropdown{display:block}

/* 사용자 영역 */
.nav-right{display:flex;align-items:center;gap:8px;margin-left:auto;white-space:nowrap}
.nav-user{position:relative}
.nav-username{color:#fff;font-size:.85rem;padding:6px 12px;border-radius:6px;cursor:pointer;
              display:flex;align-items:center;gap:6px;background:rgba(255,255,255,.1);transition:.15s}
.nav-username:hover{background:rgba(255,255,255,.18)}
.user-dd{display:none;position:absolute;right:0;top:calc(100%+8px);background:#fff;
         border-radius:8px;box-shadow:0 6px 20px rgba(0,0,0,.14);min-width:140px;overflow:hidden;z-index:999}
.user-dd a{display:block;padding:11px 16px;color:#333;font-size:.86rem;border-bottom:1px solid #f0f0f0;transition:.12s}
.user-dd a:last-child{border-bottom:none;color:#e74c3c}
.user-dd a:hover{background:#f5f5f5}
.nav-user:hover .user-dd{display:block}
.btn-login{padding:6px 13px;border-radius:6px;color:#fff;font-size:.83rem;
           border:1px solid rgba(255,255,255,.35);transition:.15s}
.btn-login:hover{background:rgba(255,255,255,.1)}
.btn-signup{padding:6px 13px;border-radius:6px;background:#27ae60;color:#fff;
            font-size:.83rem;font-weight:700;transition:.15s}
.btn-signup:hover{background:#219a52}

/* 모바일 토글 */
.nav-toggle{display:none;background:none;border:none;color:#fff;font-size:1.25rem;cursor:pointer;padding:4px 8px}

/* ── 공통 컴포넌트 ── */
.container{max-width:1200px;margin:0 auto;padding:30px 20px}
.card{background:#fff;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,.07);padding:24px;margin-bottom:20px}
.card-title{font-size:.95rem;font-weight:700;color:#1c2e4a;margin-bottom:16px;
            display:flex;align-items:center;gap:8px}
.page-header{margin-bottom:24px}
.page-header h1{font-size:1.6rem;font-weight:800;color:#1c2e4a}
.page-header p{color:#777;font-size:.88rem;margin-top:5px}

/* 버튼 */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;
     padding:9px 20px;border-radius:7px;font-size:.9rem;font-weight:700;
     cursor:pointer;border:none;transition:.15s;text-align:center}
.btn:disabled{opacity:.5;cursor:default}
.btn-primary{background:#1a5276;color:#fff}.btn-primary:hover{background:#154360}
.btn-success{background:#27ae60;color:#fff}.btn-success:hover{background:#219a52}
.btn-outline{background:#fff;color:#1c2e4a;border:2px solid #1c2e4a}
.btn-outline:hover{background:#1c2e4a;color:#fff}
.btn-danger{background:#e74c3c;color:#fff}.btn-danger:hover{background:#c0392b}
.btn-sm{padding:5px 12px;font-size:.8rem}
.btn-lg{padding:12px 28px;font-size:1rem}

/* 배지 */
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:.73rem;font-weight:700}
.badge-green{background:#d5f5e3;color:#1e8449}
.badge-red{background:#fadbd8;color:#c0392b}
.badge-blue{background:#d6eaf8;color:#1a5276}
.badge-gray{background:#f0f0f0;color:#666}

/* 폼 */
.form-group{margin-bottom:18px}
.form-group label{display:block;font-size:.84rem;font-weight:600;color:#444;margin-bottom:6px}
.form-group input,.form-group select{width:100%;padding:10px 13px;
  border:1.5px solid #ddd;border-radius:7px;font-size:.9rem;transition:.15s;outline:none;
  font-family:inherit}
.form-group input:focus,.form-group select:focus{border-color:#1a5276;
  box-shadow:0 0 0 3px rgba(26,82,118,.1)}
.form-hint{font-size:.78rem;color:#999;margin-top:4px}
.form-error{font-size:.8rem;color:#e74c3c;margin-top:5px;display:flex;align-items:center;gap:4px}
.alert{padding:12px 16px;border-radius:8px;font-size:.88rem;margin-bottom:16px}
.alert-error{background:#fdedec;color:#c0392b;border:1px solid #fadbd8}
.alert-success{background:#eafaf1;color:#1e8449;border:1px solid #d5f5e3}
.alert-info{background:#eaf4fd;color:#1a5276;border:1px solid #d6eaf8}

/* 구분선 */
.divider{border:none;border-top:1px solid #eee;margin:20px 0}

/* 푸터 */
footer{background:#1c2e4a;color:rgba(255,255,255,.5);text-align:center;
       padding:18px 20px;font-size:.77rem;line-height:1.9;margin-top:auto}
footer a{color:rgba(255,255,255,.7)}
footer a:hover{color:#fff}

/* 반응형 */
@media(max-width:768px){
  .nav-toggle{display:block}
  .nav-menu{display:none;flex-direction:column;position:absolute;
            top:58px;left:0;right:0;background:#1c2e4a;padding:6px 0;gap:0}
  .nav-menu.open{display:flex}
  .has-dd .dropdown{position:static;box-shadow:none;background:rgba(0,0,0,.2);border-radius:0}
  .has-dd .dropdown a{color:rgba(255,255,255,.75);padding-left:32px;border-color:rgba(255,255,255,.07)}
  .nav-right{margin-left:auto}
}
"""

def layout(title: str, body: str, session=None,
           active: str = "", extra_css: str = "", extra_js: str = "") -> str:

    if session:
        user_html = f"""
        <div class="nav-user">
            <div class="nav-username">👤 {session['name']}<span class="caret">▾</span></div>
            <div class="user-dd">
                <a href="/mypage">✏️ 내 정보</a>
                <a href="/logout">로그아웃</a>
            </div>
        </div>"""
    else:
        user_html = """
        <a href="/login" class="btn-login">로그인</a>
        <a href="/signup" class="btn-signup">회원가입</a>"""

    def ni(label, href, key, icon="", sub=None):
        cls = "nav-item has-dd" if sub else "nav-item"
        if active == key: cls += " active"
        if sub:
            sub_html = "".join(
                f'<a href="{h}">{i} {l}</a>' for l, h, i in sub
            )
            return (f'<div class="{cls}">'
                    f'<a href="{href}">{icon} {label}<span class="caret">▾</span></a>'
                    f'<div class="dropdown">{sub_html}</div></div>')
        return f'<div class="{cls}"><a href="{href}">{icon} {label}</a></div>'

    nav = f"""
<nav class="navbar">
  <div class="nav-inner">
    <a href="/" class="nav-brand">🎾 김포 테니스</a>
    <button class="nav-toggle" onclick="toggleNav()">☰</button>
    <div class="nav-menu" id="navMenu">
      {ni('소개',      '/intro',         'intro',  '🏠')}
      {ni('코트현황',  '/court/parcos',   'court',  '🏟️',
          [('파르코스 테니스장', '/court/parcos', '🎾')])}
      {ni('참여현황',  '/stats',          'stats',  '📊')}
    </div>
    <div class="nav-right">{user_html}</div>
  </div>
</nav>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | 김포 테니스</title>
<style>{_COMMON_CSS}{extra_css}</style>
</head>
<body>
{nav}
<div style="flex:1">{body}</div>
<footer>
  <div>김포시체육회 파르코스 테니스장 코트 현황 대시보드</div>
  <div style="margin-top:3px">
    <a href="http://www.gimposports.or.kr" target="_blank">김포시체육회 공식 사이트</a>
    &nbsp;·&nbsp; 고촌읍 신곡로 114-13 &nbsp;·&nbsp; 문의 010-6767-4994
  </div>
</footer>
<script>
function toggleNav(){{document.getElementById('navMenu').classList.toggle('open')}}
{extra_js}
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════
#  5. 페이지 – 소개
# ═══════════════════════════════════════════════════════════════
def page_intro(session):
    steps = [
        ("1", "홈페이지 로그인", "김포시체육회 사이트에 회원가입 후 로그인"),
        ("2", "코트 선택", "파르코스 테니스장에서 원하는 코트를 선택"),
        ("3", "날짜·시간 선택", "예약 가능한 날짜와 시간대를 확인"),
        ("4", "신청 및 결제", "예약 신청 후 기한 내 사용료 입금"),
        ("5", "관리실 방문", "이용 당일 관리사무실에서 확인"),
    ]
    step_html = "".join(f"""
        <div style="display:flex;align-items:flex-start;gap:14px;padding:14px 0;
                    border-bottom:1px solid #f0f0f0">
            <div style="min-width:32px;height:32px;border-radius:50%;background:#1c2e4a;
                        color:#fff;font-weight:800;display:flex;align-items:center;
                        justify-content:center;font-size:.85rem">{n}</div>
            <div>
                <div style="font-weight:700;margin-bottom:2px">{t}</div>
                <div style="font-size:.83rem;color:#777">{d}</div>
            </div>
        </div>""" for n, t, d in steps)

    notice_items = [
        "1일 1타임(2시간)만 대관 신청 가능",
        "당일 예약은 사용시간 1시간 전까지 인터넷 신청",
        "예약 후 미결제 시 자동 취소",
        "예약일 전일 17시까지 결제 처리 필수",
        "관외 거주자 사용료 50% 가산",
    ]
    notice_html = "".join(
        f'<li style="padding:5px 0;font-size:.85rem;color:#555">✔ {i}</li>'
        for i in notice_items
    )

    body = f"""
<div class="container">

  <!-- 히어로 -->
  <div style="background:linear-gradient(135deg,#1c2e4a,#2e86c1);border-radius:16px;
              padding:48px 36px;text-align:center;margin-bottom:24px;color:#fff">
    <div style="font-size:3.5rem;margin-bottom:14px">🎾</div>
    <h1 style="font-size:2rem;font-weight:800;letter-spacing:-.5px">
      김포 파르코스 테니스장
    </h1>
    <p style="margin-top:10px;opacity:.85;font-size:.95rem">
      코트 예약 현황을 실시간으로 확인하고 빠르게 예약하세요
    </p>
    <a href="/court/parcos" class="btn btn-success btn-lg" style="margin-top:22px">
      🏟️ 코트 현황 바로보기
    </a>
  </div>

  <!-- 키 정보 카드 4개 -->
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-bottom:24px">
    <div class="card" style="text-align:center;padding:20px">
      <div style="font-size:2rem;margin-bottom:8px">📍</div>
      <div style="font-weight:700;margin-bottom:4px;font-size:.95rem">위치</div>
      <div style="font-size:.82rem;color:#666;line-height:1.6">김포시 고촌읍<br>신곡로 114-13</div>
    </div>
    <div class="card" style="text-align:center;padding:20px">
      <div style="font-size:2rem;margin-bottom:8px">⏰</div>
      <div style="font-weight:700;margin-bottom:4px;font-size:.95rem">운영시간</div>
      <div style="font-size:.82rem;color:#666;line-height:1.6">매일<br>06:00 ~ 23:00</div>
    </div>
    <div class="card" style="text-align:center;padding:20px">
      <div style="font-size:2rem;margin-bottom:8px">🏟️</div>
      <div style="font-weight:700;margin-bottom:4px;font-size:.95rem">코트 수</div>
      <div style="font-size:.82rem;color:#666;line-height:1.6">총 8면<br>(1코트 ~ 8코트)</div>
    </div>
    <div class="card" style="text-align:center;padding:20px">
      <div style="font-size:2rem;margin-bottom:8px">📞</div>
      <div style="font-weight:700;margin-bottom:4px;font-size:.95rem">문의</div>
      <div style="font-size:.82rem;color:#666;line-height:1.6">010-6767-4994<br>070-4647-0741</div>
    </div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">

    <!-- 사용료 -->
    <div class="card">
      <div class="card-title">💰 사용료 <span style="font-size:.75rem;font-weight:400;color:#999">(2시간 1타임 1면)</span></div>
      <table style="width:100%;border-collapse:collapse;font-size:.86rem">
        <thead>
          <tr style="background:#f0f4f8">
            <th style="padding:9px 12px;text-align:left;border-radius:6px 0 0 6px;font-weight:600">구분</th>
            <th style="padding:9px;text-align:center;font-weight:600">주간</th>
            <th style="padding:9px;text-align:center;border-radius:0 6px 6px 0;font-weight:600">야간</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style="padding:9px 12px;border-bottom:1px solid #f0f0f0">평일</td>
            <td style="padding:9px;text-align:center;border-bottom:1px solid #f0f0f0">10,000원</td>
            <td style="padding:9px;text-align:center;border-bottom:1px solid #f0f0f0">20,000원</td>
          </tr>
          <tr>
            <td style="padding:9px 12px">주말·공휴일</td>
            <td style="padding:9px;text-align:center">20,000원</td>
            <td style="padding:9px;text-align:center">30,000원</td>
          </tr>
        </tbody>
      </table>
      <p style="font-size:.76rem;color:#999;margin-top:10px">※ 관외 거주자 50% 가산</p>
    </div>

    <!-- 유의사항 -->
    <div class="card">
      <div class="card-title">📋 유의사항</div>
      <ul style="list-style:none;padding:0">{notice_html}</ul>
    </div>

  </div>

  <!-- 예약 방법 -->
  <div class="card">
    <div class="card-title">🚀 예약 방법</div>
    {step_html}
    <div style="margin-top:14px;text-align:center">
      <a href="http://www.gimposports.or.kr/bbs/orderCourse.php"
         target="_blank" class="btn btn-primary">
        🔗 공식 예약 사이트 바로가기
      </a>
    </div>
  </div>

</div>"""
    return layout("소개", body, session, "intro")


# ═══════════════════════════════════════════════════════════════
#  6. 페이지 – 코트현황 (파르코스 테니스장)
# ═══════════════════════════════════════════════════════════════
def page_court_parcos(session):
    css = """
.date-tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px}
.dtab{padding:5px 13px;border-radius:20px;background:#fff;border:2px solid #ccc;
      cursor:pointer;font-size:.8rem;font-weight:600;transition:all .15s;white-space:nowrap}
.dtab.active{background:#1c2e4a;color:#fff;border-color:#1c2e4a}
.dtab:hover:not(.active){border-color:#1c2e4a;color:#1c2e4a}
.ctrl-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:18px}
.ctrl-bar label{font-size:.83rem;color:#555;font-weight:600}
.ctrl-bar input,.ctrl-bar select{padding:7px 11px;border:1.5px solid #ddd;
  border-radius:7px;font-size:.88rem;outline:none;font-family:inherit}
.ctrl-bar input:focus,.ctrl-bar select:focus{border-color:#1c2e4a}
.legend{display:flex;gap:14px;margin-bottom:10px;font-size:.8rem;align-items:center}
.legend span{display:inline-flex;align-items:center;gap:5px}
.dot{width:11px;height:11px;border-radius:3px;display:inline-block}
.dot-o{background:#1e8449}.dot-x{background:#c0392b}
.tbl-wrap{overflow-x:auto}
table.court-tbl{width:100%;border-collapse:collapse;font-size:.85rem;
  border-radius:10px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.07)}
.court-tbl th{background:#1c2e4a;color:#fff;padding:10px 8px;text-align:center;
              white-space:nowrap;font-weight:600}
.court-tbl td{padding:7px 6px;text-align:center;border-bottom:1px solid #eee}
.court-tbl tr:last-child td{border-bottom:none}
.court-tbl tr:hover td{background:#f7fafc}
.tc{font-weight:700;color:#444;white-space:nowrap}
.slot-o{background:#d5f5e3;color:#1e8449;font-weight:700;border-radius:5px;
        padding:3px 0;display:block}
.slot-x{background:#fadbd8;color:#c0392b;border-radius:5px;padding:3px 0;display:block}
.slot-na{color:#ccc}
.night-sep td{border-top:2.5px solid #2e86c1}
#status-msg{text-align:center;padding:40px;color:#888;font-size:.95rem}
.updated{font-size:.75rem;color:#aaa;margin-bottom:8px}
.sub-header{background:#f8f9fc;border-radius:10px;padding:14px 18px;
            margin-bottom:18px;display:flex;align-items:center;gap:10px;
            border-left:4px solid #2e86c1}
"""
    js = """
let _curDate='';

(function buildTabs(){
  const nav=document.getElementById('dateTabs');
  const days=['일','월','화','수','목','금','토'];
  const today=new Date();
  for(let i=0;i<14;i++){
    const d=new Date(today); d.setDate(today.getDate()+i);
    const ymd=d.toISOString().slice(0,10).replace(/-/g,'');
    const dow=days[d.getDay()];
    const label=`${d.getMonth()+1}/${d.getDate()}(${dow})`;
    const tab=document.createElement('div');
    tab.className='dtab'+(i===0?' active':'');
    if(d.getDay()===0) tab.style.color='#e74c3c';
    if(d.getDay()===6) tab.style.color='#2e86c1';
    tab.textContent=label; tab.dataset.ymd=ymd;
    tab.onclick=()=>{
      document.querySelectorAll('.dtab').forEach(t=>t.classList.remove('active'));
      tab.classList.add('active');
      loadData(ymd);
    };
    nav.appendChild(tab);
    if(i===0) _curDate=ymd;
  }
})();

function setLoading(on){
  document.getElementById('status-msg').textContent=on?'⏳ 조회 중...':'';
  document.getElementById('status-msg').style.display=on?'':'none';
  document.getElementById('courtResult').style.display=on?'none':'';
}

async function loadData(date){
  if(typeof date !== 'string' || date.length!==8) date=_curDate;
  _curDate=date;
  setLoading(true);
  try{
    const r=await fetch(`/api/slots?date=${date}&unit=1`);
    if(!r.ok) throw new Error('서버 오류 '+r.status);
    renderTable(await r.json());
  }catch(e){
    document.getElementById('status-msg').textContent='❌ 조회 실패: '+e.message;
    document.getElementById('status-msg').style.display='';
    document.getElementById('courtResult').style.display='none';
  }
}

function renderTable(data){
  const allT=new Set();
  Object.values(data).forEach(v=>(v.slots||[]).forEach(s=>allT.add(s.time)));
  const times=[...allT].sort();
  const rooms=Object.keys(data);

  // 헤더
  document.getElementById('thead').innerHTML=
    '<tr><th>시간</th>'+rooms.map(r=>`<th>${data[r].name}</th>`).join('')+'</tr>';

  // 집계
  let total=0,avail=0;
  times.forEach(t=>rooms.forEach(r=>{
    const m={};(data[r].slots||[]).forEach(s=>m[s.time]=s.available);
    if(t in m){total++;if(m[t])avail++;}
  }));
  const pct=total?Math.round(avail/total*100):0;
  document.getElementById('courtSummary').innerHTML=
    `<span class="badge badge-green">○ 가능 ${avail}</span> `+
    `<span class="badge badge-red">× 예약됨 ${total-avail}</span> `+
    `<span class="badge badge-blue">전체 ${total}슬롯 · 가용률 ${pct}%</span>`;

  // 바디
  const tbody=document.getElementById('tbody');
  tbody.innerHTML='';
  times.forEach(t=>{
    const tr=document.createElement('tr');
    if(t==='18:00') tr.classList.add('night-sep');
    const td0=document.createElement('td'); td0.className='tc'; td0.textContent=t;
    tr.appendChild(td0);
    rooms.forEach(r=>{
      const m={};(data[r].slots||[]).forEach(s=>m[s.time]=s.available);
      const td=document.createElement('td');
      if(!(t in m)){td.className='slot-na';td.textContent='-';}
      else if(m[t]){td.innerHTML='<span class=\\"slot-o\\">○</span>';}
      else{td.innerHTML='<span class=\\"slot-x\\">×</span>';}
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });

  document.getElementById('updatedAt').textContent=
    '조회: '+new Date().toLocaleTimeString('ko-KR');
  document.getElementById('status-msg').style.display='none';
  document.getElementById('courtResult').style.display='';
}

window.addEventListener('load', loadData);
"""
    body = """
<div class="container">
  <div class="page-header">
    <h1>🏟️ 코트 현황</h1>
    <p>실시간 예약 가능 시간을 확인하세요</p>
  </div>

  <div class="sub-header">
    <span style="font-size:1.2rem">🎾</span>
    <div>
      <div style="font-weight:700;font-size:.95rem">파르코스 테니스장</div>
      <div style="font-size:.8rem;color:#777;margin-top:2px">고촌읍 신곡로 114-13 · 06:00~23:00 · 8면</div>
    </div>
    <a href="http://www.gimposports.or.kr/bbs/orderCourse.php" target="_blank"
       class="btn btn-primary btn-sm" style="margin-left:auto">공식 예약 →</a>
  </div>

  <div class="card">
    <!-- 날짜 탭 -->
    <div class="date-tabs" id="dateTabs"></div>

    <!-- 결과 -->
    <div id="status-msg"></div>
    <div id="courtResult" style="display:none">
      <div class="legend">
        <span><span class="dot dot-o"></span> 예약 가능</span>
        <span><span class="dot dot-x"></span> 예약 불가</span>
        <span style="color:#2e86c1;font-weight:600">│ = 야간 구분</span>
      </div>
      <div id="courtSummary" style="margin-bottom:8px"></div>
      <div class="updated" id="updatedAt"></div>
      <div class="tbl-wrap">
        <table class="court-tbl">
          <thead id="thead"></thead>
          <tbody id="tbody"></tbody>
        </table>
      </div>
    </div>
  </div>
</div>"""

    return layout("코트현황 – 파르코스", body, session, "court",
                  extra_css=css, extra_js=js)


# ═══════════════════════════════════════════════════════════════
#  7. 페이지 – 참여현황
# ═══════════════════════════════════════════════════════════════
def page_stats(session):
    css = """
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin-bottom:20px}
.stat-card{background:#fff;border-radius:10px;padding:18px;text-align:center;
           box-shadow:0 2px 8px rgba(0,0,0,.07)}
.stat-num{font-size:2rem;font-weight:800;line-height:1.1}
.stat-label{font-size:.78rem;color:#888;margin-top:5px}
.bar-wrap{margin-bottom:10px}
.bar-label{display:flex;justify-content:space-between;font-size:.82rem;margin-bottom:4px}
.bar-bg{background:#f0f0f0;border-radius:20px;height:10px;overflow:hidden}
.bar-fill{height:10px;border-radius:20px;transition:width .5s;background:#27ae60}
.heatmap-row{display:flex;align-items:center;gap:6px;margin-bottom:5px}
.heatmap-time{width:50px;font-size:.78rem;color:#666;text-align:right;flex-shrink:0}
.heatmap-cells{display:flex;gap:3px;flex:1}
.hm-cell{flex:1;height:22px;border-radius:3px;transition:.3s}
.hm-0{background:#1e8449}
.hm-25{background:#82e0aa}
.hm-50{background:#f9e79f}
.hm-75{background:#f0b27a}
.hm-100{background:#e74c3c}
.hm-na{background:#f0f0f0}
.date-tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px}
.dtab{padding:5px 12px;border-radius:20px;background:#fff;border:2px solid #ccc;
      cursor:pointer;font-size:.79rem;font-weight:600;transition:.15s;white-space:nowrap}
.dtab.active{background:#1c2e4a;color:#fff;border-color:#1c2e4a}
.dtab:hover:not(.active){border-color:#1c2e4a;color:#1c2e4a}
"""
    js = """
(function buildTabs(){
  const nav=document.getElementById('statsTabs');
  const pk=document.getElementById('statDate');
  const days=['일','월','화','수','목','금','토'];
  const today=new Date();
  for(let i=0;i<7;i++){
    const d=new Date(today); d.setDate(today.getDate()+i);
    const ymd=d.toISOString().slice(0,10).replace(/-/g,'');
    const label=`${d.getMonth()+1}/${d.getDate()}(${days[d.getDay()]})`;
    const tab=document.createElement('div');
    tab.className='dtab'+(i===0?' active':'');
    tab.textContent=label; tab.dataset.ymd=ymd;
    tab.onclick=()=>{
      document.querySelectorAll('#statsTabs .dtab').forEach(t=>t.classList.remove('active'));
      tab.classList.add('active');
      pk.value=`${ymd.slice(0,4)}-${ymd.slice(4,6)}-${ymd.slice(6,8)}`;
      loadStats();
    };
    nav.appendChild(tab);
    if(i===0) pk.value=`${ymd.slice(0,4)}-${ymd.slice(4,6)}-${ymd.slice(6,8)}`;
  }
})();

async function loadStats(){
  const date=document.getElementById('statDate').value.replace(/-/g,'');
  if(!date) return;
  document.getElementById('statsContent').style.display='none';
  document.getElementById('statsMsg').style.display='';
  document.getElementById('statsMsg').textContent='⏳ 조회 중...';
  document.querySelectorAll('#statsTabs .dtab').forEach(t=>{
    t.classList.toggle('active',t.dataset.ymd===date);
  });
  try{
    const r=await fetch(`/api/slots?date=${date}&unit=1`);
    if(!r.ok) throw new Error('서버 오류');
    renderStats(await r.json(), date);
  }catch(e){
    document.getElementById('statsMsg').textContent='❌ 조회 실패: '+e.message;
  }
}

function renderStats(data, date){
  const rooms=Object.keys(data);
  const allT=new Set();
  rooms.forEach(r=>(data[r].slots||[]).forEach(s=>allT.add(s.time)));
  const times=[...allT].sort();

  // 전체 통계
  let total=0,avail=0;
  times.forEach(t=>rooms.forEach(r=>{
    const m={};(data[r].slots||[]).forEach(s=>m[s.time]=s.available);
    if(t in m){total++;if(m[t])avail++;}
  }));
  const booked=total-avail;
  const pct=total?Math.round(booked/total*100):0;

  document.getElementById('s-total').textContent=total;
  document.getElementById('s-avail').textContent=avail;
  document.getElementById('s-booked').textContent=booked;
  document.getElementById('s-rate').textContent=pct+'%';

  // 코트별 바
  const barsDiv=document.getElementById('courtBars');
  barsDiv.innerHTML='';
  rooms.forEach(r=>{
    const slotsMap={};(data[r].slots||[]).forEach(s=>slotsMap[s.time]=s.available);
    const rTotal=Object.keys(slotsMap).length;
    const rBooked=Object.values(slotsMap).filter(v=>!v).length;
    const rPct=rTotal?Math.round(rBooked/rTotal*100):0;
    const col=rPct>=80?'#e74c3c':rPct>=50?'#f39c12':'#27ae60';
    barsDiv.innerHTML+=`
      <div class="bar-wrap">
        <div class="bar-label">
          <span style="font-weight:600">${data[r].name}</span>
          <span style="color:#888">${rBooked}/${rTotal} 예약됨 (${rPct}%)</span>
        </div>
        <div class="bar-bg"><div class="bar-fill" style="width:${rPct}%;background:${col}"></div></div>
      </div>`;
  });

  // 시간대별 히트맵
  const hmDiv=document.getElementById('heatmap');
  hmDiv.innerHTML='<div style="display:flex;align-items:center;gap:6px;margin-bottom:8px">'
    +'<div style="width:50px"></div>'
    +'<div class="heatmap-cells" style="font-size:.7rem;color:#999">'
    +rooms.map(r=>`<div style="flex:1;text-align:center">${data[r].name}</div>`).join('')
    +'</div></div>';
  times.forEach(t=>{
    const row=document.createElement('div'); row.className='heatmap-row';
    const tlabel=document.createElement('div'); tlabel.className='heatmap-time';
    tlabel.textContent=t; row.appendChild(tlabel);
    const cells=document.createElement('div'); cells.className='heatmap-cells';
    rooms.forEach(r=>{
      const m={};(data[r].slots||[]).forEach(s=>m[s.time]=s.available);
      const cell=document.createElement('div');
      if(!(t in m)){cell.className='hm-cell hm-na';}
      else if(m[t]){cell.className='hm-cell hm-0';cell.title=`${data[r].name} ${t}: 예약가능`;}
      else{cell.className='hm-cell hm-100';cell.title=`${data[r].name} ${t}: 예약됨`;}
      cells.appendChild(cell);
    });
    row.appendChild(cells);
    hmDiv.appendChild(row);
  });

  document.getElementById('statsUpdated').textContent=
    `기준: ${date.slice(0,4)}-${date.slice(4,6)}-${date.slice(6,8)} · 조회: `+new Date().toLocaleTimeString('ko-KR');
  document.getElementById('statsMsg').style.display='none';
  document.getElementById('statsContent').style.display='';
}

window.addEventListener('load', loadStats);
"""
    body = """
<div class="container">
  <div class="page-header">
    <h1>📊 참여현황</h1>
    <p>날짜별 전체 코트 예약 현황과 혼잡도를 확인합니다</p>
  </div>

  <div class="card">
    <div class="date-tabs" id="statsTabs"></div>
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:16px">
      <label style="font-size:.83rem;font-weight:600;color:#555">날짜</label>
      <input type="date" id="statDate"
             style="padding:7px 11px;border:1.5px solid #ddd;border-radius:7px;font-size:.88rem;outline:none;font-family:inherit">
      <button class="btn btn-primary" onclick="loadStats()">🔍 조회</button>
      <div class="updated" id="statsUpdated" style="margin:0 0 0 auto"></div>
    </div>

    <div id="statsMsg" style="text-align:center;padding:30px;color:#888"></div>

    <div id="statsContent" style="display:none">
      <!-- 요약 -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-num" style="color:#1c2e4a" id="s-total">-</div>
          <div class="stat-label">전체 슬롯</div>
        </div>
        <div class="stat-card">
          <div class="stat-num" style="color:#27ae60" id="s-avail">-</div>
          <div class="stat-label">예약 가능</div>
        </div>
        <div class="stat-card">
          <div class="stat-num" style="color:#e74c3c" id="s-booked">-</div>
          <div class="stat-label">예약됨</div>
        </div>
        <div class="stat-card">
          <div class="stat-num" style="color:#e67e22" id="s-rate">-</div>
          <div class="stat-label">예약률</div>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <!-- 코트별 바 -->
        <div>
          <div class="card-title" style="margin-bottom:12px">🏟️ 코트별 예약률</div>
          <div id="courtBars"></div>
          <div style="display:flex;gap:12px;margin-top:10px;font-size:.75rem;color:#888">
            <span>● 여유 (0~49%)</span>
            <span style="color:#f39c12">● 보통 (50~79%)</span>
            <span style="color:#e74c3c">● 혼잡 (80%+)</span>
          </div>
        </div>
        <!-- 히트맵 -->
        <div>
          <div class="card-title" style="margin-bottom:12px">🌡️ 시간대×코트 혼잡도</div>
          <div style="display:flex;gap:12px;margin-bottom:8px;font-size:.75rem">
            <span style="display:flex;align-items:center;gap:4px">
              <span style="width:12px;height:12px;background:#1e8449;border-radius:2px;display:inline-block"></span> 가능
            </span>
            <span style="display:flex;align-items:center;gap:4px">
              <span style="width:12px;height:12px;background:#e74c3c;border-radius:2px;display:inline-block"></span> 예약됨
            </span>
            <span style="display:flex;align-items:center;gap:4px">
              <span style="width:12px;height:12px;background:#f0f0f0;border-radius:2px;display:inline-block"></span> 없음
            </span>
          </div>
          <div id="heatmap" style="overflow-x:auto"></div>
        </div>
      </div>
    </div>
  </div>
</div>"""
    return layout("참여현황", body, session, "stats",
                  extra_css=css, extra_js=js)


# ═══════════════════════════════════════════════════════════════
#  8. 페이지 – 로그인
# ═══════════════════════════════════════════════════════════════
def page_login(session, error="", redirect="/"):
    err_html = f'<div class="alert alert-error">⚠️ {error}</div>' if error else ""
    body = f"""
<div class="container" style="max-width:420px">
  <div class="page-header" style="text-align:center">
    <div style="font-size:2.5rem;margin-bottom:8px">🔐</div>
    <h1>로그인</h1>
    <p>김포 테니스 대시보드에 오신 것을 환영합니다</p>
  </div>
  <div class="card">
    {err_html}
    <form method="POST" action="/api/login">
      <input type="hidden" name="redirect" value="{redirect}">
      <div class="form-group">
        <label>아이디</label>
        <input type="text" name="uid" placeholder="아이디를 입력하세요" required autocomplete="username">
      </div>
      <div class="form-group">
        <label>비밀번호</label>
        <input type="password" name="pw" placeholder="비밀번호를 입력하세요" required autocomplete="current-password">
      </div>
      <button type="submit" class="btn btn-primary" style="width:100%;margin-top:4px">로그인</button>
    </form>
    <hr class="divider">
    <p style="text-align:center;font-size:.85rem;color:#777">
      아직 회원이 아니신가요?
      <a href="/signup" style="color:#1a5276;font-weight:700">회원가입 →</a>
    </p>
  </div>
</div>"""
    return layout("로그인", body, session)


# ═══════════════════════════════════════════════════════════════
#  9. 페이지 – 회원가입 (3단계 위자드)
# ═══════════════════════════════════════════════════════════════
def page_signup(session, error="", prefill=None):
    p = prefill or {}
    err_html = f'<div class="alert alert-error">⚠️ {error}</div>' if error else ""
    css = """
.step-bar{display:flex;align-items:center;margin-bottom:28px;gap:0}
.step{flex:1;text-align:center;position:relative}
.step-circle{width:34px;height:34px;border-radius:50%;border:2px solid #ccc;
  background:#fff;display:flex;align-items:center;justify-content:center;
  margin:0 auto 6px;font-weight:700;font-size:.85rem;color:#ccc;transition:.3s}
.step.done .step-circle{background:#27ae60;border-color:#27ae60;color:#fff}
.step.active .step-circle{background:#1c2e4a;border-color:#1c2e4a;color:#fff}
.step-label{font-size:.72rem;color:#aaa;white-space:nowrap}
.step.active .step-label{color:#1c2e4a;font-weight:700}
.step.done .step-label{color:#27ae60}
.step-line{flex:1;height:2px;background:#ccc;margin-bottom:20px}
.step-line.done{background:#27ae60}
.step-pane{display:none}.step-pane.active{display:block}
.pw-strength{height:4px;border-radius:2px;margin-top:5px;transition:.3s;background:#eee}
"""
    js = r"""
let cur=1;
function goStep(n){
  if(n>cur && !validateStep(cur)) return;
  document.querySelectorAll('.step-pane').forEach((p,i)=>{
    p.classList.toggle('active',i+1===n);
  });
  document.querySelectorAll('.step').forEach((s,i)=>{
    s.classList.remove('active','done');
    if(i+1<n) s.classList.add('done');
    if(i+1===n) s.classList.add('active');
  });
  document.querySelectorAll('.step-line').forEach((l,i)=>{
    l.classList.toggle('done',i+1<n);
  });
  cur=n;
  document.getElementById('prevBtn').style.display=n>1?'':'none';
  document.getElementById('nextBtn').style.display=n<3?'':'none';
  document.getElementById('submitBtn').style.display=n===3?'':'none';
}

function validateStep(n){
  if(n===1){
    const uid=document.getElementById('f_uid').value.trim();
    const pw=document.getElementById('f_pw').value;
    const pw2=document.getElementById('f_pw2').value;
    if(!uid||uid.length<4){alert('아이디는 4자 이상이어야 합니다.');return false;}
    if(!pw||pw.length<6){alert('비밀번호는 6자 이상이어야 합니다.');return false;}
    if(pw!==pw2){alert('비밀번호가 일치하지 않습니다.');return false;}
  }
  if(n===2){
    const name=document.getElementById('f_name').value.trim();
    const email=document.getElementById('f_email').value.trim();
    if(!name){alert('이름을 입력하세요.');return false;}
    if(email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){
      alert('올바른 이메일 형식이 아닙니다.');return false;
    }
  }
  return true;
}

function checkPwStrength(){
  const pw=document.getElementById('f_pw').value;
  const bar=document.getElementById('pwBar');
  let score=0;
  if(pw.length>=6) score++;
  if(pw.length>=10) score++;
  if(/[A-Z]/.test(pw)||/[0-9]/.test(pw)) score++;
  if(/[^A-Za-z0-9]/.test(pw)) score++;
  const colors=['#eee','#e74c3c','#f39c12','#27ae60','#1a5276'];
  const widths=['0%','30%','55%','80%','100%'];
  bar.style.background=colors[score];
  bar.style.width=widths[score];
}

// 3단계 요약 채우기
function fillSummary(){
  document.getElementById('sum-uid').textContent=document.getElementById('f_uid').value;
  document.getElementById('sum-name').textContent=document.getElementById('f_name').value;
  document.getElementById('sum-email').textContent=document.getElementById('f_email').value||'(없음)';
  document.getElementById('sum-phone').textContent=document.getElementById('f_phone').value||'(없음)';
  document.getElementById('sum-area').textContent=
    document.getElementById('f_area').value==='1'?'김포시 거주':'타 지역';
}

window.addEventListener('load',()=>goStep(1));
"""
    body = f"""
<div class="container" style="max-width:480px">
  <div class="page-header" style="text-align:center">
    <div style="font-size:2.5rem;margin-bottom:8px">✨</div>
    <h1>회원가입</h1>
    <p>간단한 정보를 입력해 시작하세요</p>
  </div>
  <div class="card">
    {err_html}

    <!-- 단계 표시바 -->
    <div class="step-bar">
      <div class="step active" id="step1"><div class="step-circle">1</div><div class="step-label">계정 정보</div></div>
      <div class="step-line" id="line1"></div>
      <div class="step" id="step2"><div class="step-circle">2</div><div class="step-label">개인 정보</div></div>
      <div class="step-line" id="line2"></div>
      <div class="step" id="step3"><div class="step-circle">3</div><div class="step-label">확인</div></div>
    </div>

    <form method="POST" action="/api/signup" id="signupForm">

      <!-- STEP 1: 계정 정보 -->
      <div class="step-pane" id="pane1">
        <div class="form-group">
          <label>아이디 <span style="color:#e74c3c">*</span></label>
          <input type="text" id="f_uid" name="uid" placeholder="4~20자 영문, 숫자"
                 value="{p.get('uid','')}" autocomplete="username">
          <div class="form-hint">영문, 숫자 조합 4~20자</div>
        </div>
        <div class="form-group">
          <label>비밀번호 <span style="color:#e74c3c">*</span></label>
          <input type="password" id="f_pw" name="pw" placeholder="6자 이상"
                 oninput="checkPwStrength()" autocomplete="new-password">
          <div class="pw-strength" style="width:0%"><div class="pw-strength" id="pwBar" style="width:0%;margin:0"></div></div>
        </div>
        <div class="form-group">
          <label>비밀번호 확인 <span style="color:#e74c3c">*</span></label>
          <input type="password" id="f_pw2" name="pw2" placeholder="비밀번호 재입력" autocomplete="new-password">
        </div>
      </div>

      <!-- STEP 2: 개인 정보 -->
      <div class="step-pane" id="pane2">
        <div class="form-group">
          <label>이름 <span style="color:#e74c3c">*</span></label>
          <input type="text" id="f_name" name="name" placeholder="실명 입력" value="{p.get('name','')}">
        </div>
        <div class="form-group">
          <label>이메일</label>
          <input type="email" id="f_email" name="email" placeholder="example@email.com" value="{p.get('email','')}">
        </div>
        <div class="form-group">
          <label>전화번호</label>
          <input type="tel" id="f_phone" name="phone" placeholder="010-0000-0000" value="{p.get('phone','')}">
        </div>
        <div class="form-group">
          <label>거주 지역</label>
          <select id="f_area" name="area">
            <option value="1">김포시 거주 (관내)</option>
            <option value="2">타 지역 (관외)</option>
          </select>
          <div class="form-hint">관외 거주자는 사용료 50% 가산됩니다</div>
        </div>
      </div>

      <!-- STEP 3: 확인 -->
      <div class="step-pane" id="pane3">
        <div class="alert alert-info" style="margin-bottom:16px">
          아래 정보로 가입합니다. 확인 후 완료 버튼을 누르세요.
        </div>
        <table style="width:100%;font-size:.88rem;border-collapse:collapse">
          <tr><td style="padding:8px 0;color:#888;width:90px">아이디</td><td style="font-weight:700" id="sum-uid"></td></tr>
          <tr><td style="padding:8px 0;color:#888">이름</td><td id="sum-name"></td></tr>
          <tr><td style="padding:8px 0;color:#888">이메일</td><td id="sum-email"></td></tr>
          <tr><td style="padding:8px 0;color:#888">전화번호</td><td id="sum-phone"></td></tr>
          <tr><td style="padding:8px 0;color:#888">거주지</td><td id="sum-area"></td></tr>
        </table>
        <div style="margin-top:16px;padding:12px;background:#fff9e6;border-radius:7px;
                    border:1px solid #f9e79f;font-size:.8rem;color:#7d6608">
          ⚠️ 이 계정은 대시보드 전용입니다. 공식 예약은
          <a href="http://www.gimposports.or.kr" target="_blank" style="color:#1a5276">
          김포시체육회 사이트</a>에서 별도 가입이 필요합니다.
        </div>
      </div>

      <!-- 버튼 -->
      <div style="display:flex;justify-content:space-between;margin-top:22px;gap:10px">
        <button type="button" class="btn btn-outline" id="prevBtn"
                onclick="goStep(cur-1)" style="display:none">← 이전</button>
        <button type="button" class="btn btn-primary" id="nextBtn"
                onclick="cur===2?fillSummary():null;goStep(cur+1)" style="margin-left:auto">다음 →</button>
        <button type="submit" class="btn btn-success" id="submitBtn" style="display:none">✅ 가입 완료</button>
      </div>
    </form>

    <hr class="divider">
    <p style="text-align:center;font-size:.84rem;color:#777">
      이미 계정이 있으신가요?
      <a href="/login" style="color:#1a5276;font-weight:700">로그인 →</a>
    </p>
  </div>
</div>"""
    return layout("회원가입", body, session, extra_css=css, extra_js=js)


# ═══════════════════════════════════════════════════════════════
# 10. 페이지 – 내 정보
# ═══════════════════════════════════════════════════════════════
def page_mypage(session):
    if not session:
        return None  # redirect to login
    users = load_users()
    u = users.get(session["uid"], {})
    area_label = "김포시 거주 (관내)" if u.get("area") == "1" else "타 지역 (관외)"
    joined = u.get("joined", "-")

    body = f"""
<div class="container" style="max-width:540px">
  <div class="page-header">
    <h1>👤 내 정보</h1>
    <p>가입된 계정 정보를 확인합니다</p>
  </div>

  <div class="card">
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:20px">
      <div style="width:60px;height:60px;border-radius:50%;background:#1c2e4a;
                  display:flex;align-items:center;justify-content:center;
                  font-size:1.6rem;color:#fff;flex-shrink:0">
        {session['name'][0]}
      </div>
      <div>
        <div style="font-size:1.2rem;font-weight:800;color:#1c2e4a">{session['name']}</div>
        <div style="font-size:.82rem;color:#999;margin-top:2px">@{session['uid']}</div>
        <span class="badge badge-blue" style="margin-top:4px">{area_label}</span>
      </div>
    </div>

    <table style="width:100%;font-size:.88rem;border-collapse:collapse">
      <tr style="border-bottom:1px solid #f0f0f0">
        <td style="padding:10px 0;color:#888;width:100px">아이디</td>
        <td style="padding:10px 0;font-weight:600">{session['uid']}</td>
      </tr>
      <tr style="border-bottom:1px solid #f0f0f0">
        <td style="padding:10px 0;color:#888">이름</td>
        <td style="padding:10px 0">{session['name']}</td>
      </tr>
      <tr style="border-bottom:1px solid #f0f0f0">
        <td style="padding:10px 0;color:#888">이메일</td>
        <td style="padding:10px 0">{u.get('email') or '<span style="color:#ccc">-</span>'}</td>
      </tr>
      <tr style="border-bottom:1px solid #f0f0f0">
        <td style="padding:10px 0;color:#888">전화번호</td>
        <td style="padding:10px 0">{u.get('phone') or '<span style="color:#ccc">-</span>'}</td>
      </tr>
      <tr>
        <td style="padding:10px 0;color:#888">가입일</td>
        <td style="padding:10px 0">{joined}</td>
      </tr>
    </table>
  </div>

  <div class="card">
    <div class="card-title">⚙️ 계정 관리</div>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <a href="/court/parcos" class="btn btn-primary">🏟️ 코트 현황 보기</a>
      <a href="/logout" class="btn btn-danger">로그아웃</a>
    </div>
  </div>

  <div class="card">
    <div class="card-title">ℹ️ 안내</div>
    <div style="font-size:.84rem;color:#666;line-height:1.8">
      이 대시보드는 코트 현황 조회 전용 서비스입니다.<br>
      실제 예약은
      <a href="http://www.gimposports.or.kr/bbs/orderCourse.php"
         target="_blank" style="color:#1a5276;font-weight:700">
        김포시체육회 공식 사이트
      </a>에서 진행하세요.
    </div>
  </div>
</div>"""
    return layout("내 정보", body, session, extra_css="")


# ═══════════════════════════════════════════════════════════════
# 11. HTTP 핸들러
# ═══════════════════════════════════════════════════════════════
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} [{datetime.now().strftime('%H:%M:%S')}] {fmt % args}")

    # ── 쿠키 ──
    def _get_tok(self):
        raw = self.headers.get("Cookie", "")
        jar = http_cookies.SimpleCookie(raw)
        return jar["sid"].value if "sid" in jar else None

    def _get_session(self):
        return get_session(self._get_tok())

    # ── 응답 ──
    def _html(self, html: str, code=200):
        b = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(b))
        self.end_headers()
        self.wfile.write(b)

    def _json(self, data, code=200):
        b = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(b))
        self.end_headers()
        self.wfile.write(b)

    def _redirect(self, url, code=302, cookie=None, clear_cookie=False):
        self.send_response(code)
        self.send_header("Location", url)
        if cookie:
            self.send_header("Set-Cookie",
                f"sid={cookie}; Path=/; HttpOnly; Max-Age={86400*7}")
        if clear_cookie:
            self.send_header("Set-Cookie",
                "sid=; Path=/; HttpOnly; Max-Age=0")
        self.end_headers()

    # ── POST body ──
    def _post_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")
        return {k: v[0] if len(v)==1 else v
                for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()}

    # ── GET ──
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path
        query  = urllib.parse.parse_qs(parsed.query)
        sess   = self._get_session()

        if path in ("/", "/intro"):
            self._html(page_intro(sess))
        elif path == "/court" or path == "/court/":
            self._redirect("/court/parcos")
        elif path == "/court/parcos":
            self._html(page_court_parcos(sess))
        elif path == "/stats":
            self._html(page_stats(sess))
        elif path == "/login":
            if sess: self._redirect("/")
            else: self._html(page_login(sess))
        elif path == "/signup":
            if sess: self._redirect("/mypage")
            else: self._html(page_signup(sess))
        elif path == "/logout":
            tok = self._get_tok()
            if tok: del_session(tok)
            self._redirect("/", clear_cookie=True)
        elif path == "/mypage":
            if not sess:
                self._redirect("/login")
            else:
                self._html(page_mypage(sess))
        elif path == "/api/slots":
            self._api_slots(query)
        else:
            self._html("<h1>404</h1>", 404)

    # ── POST ──
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/login":
            self._api_login()
        elif path == "/api/signup":
            self._api_signup()
        else:
            self._html("<h1>404</h1>", 404)

    # ── API: 슬롯 조회 ──
    def _api_slots(self, query):
        date = query.get("date", [""])[0]
        unit = int(query.get("unit", ["1"])[0])
        if not re.fullmatch(r"\d{8}", date):
            self._json({"error": "date 파라미터 오류"}, 400); return
        try:
            self._json(get_all_slots(date, unit))
        except Exception as e:
            self._json({"error": str(e)}, 500)

    # ── API: 로그인 ──
    def _api_login(self):
        data = self._post_body()
        uid  = data.get("uid", "").strip()
        pw   = data.get("pw",  "")
        redir = data.get("redirect", "/")

        users = load_users()
        u = users.get(uid)
        if not u or u.get("pw") != hash_pw(pw):
            self._html(page_login(None, "아이디 또는 비밀번호가 틀렸습니다.", redir))
            return
        tok = new_session(uid, u["name"], u.get("email",""))
        self._redirect(redir or "/", cookie=tok)

    # ── API: 회원가입 ──
    def _api_signup(self):
        data  = self._post_body()
        uid   = data.get("uid",   "").strip()
        pw    = data.get("pw",    "")
        pw2   = data.get("pw2",   "")
        name  = data.get("name",  "").strip()
        email = data.get("email", "").strip()
        phone = data.get("phone", "").strip()
        area  = data.get("area",  "1")

        prefill = {"uid": uid, "name": name, "email": email, "phone": phone}

        # 유효성 검사
        if not uid or len(uid) < 4:
            self._html(page_signup(None, "아이디는 4자 이상이어야 합니다.", prefill)); return
        if not re.fullmatch(r"[a-zA-Z0-9_]{4,20}", uid):
            self._html(page_signup(None, "아이디는 영문, 숫자, 밑줄(_)만 사용 가능합니다.", prefill)); return
        if not pw or len(pw) < 6:
            self._html(page_signup(None, "비밀번호는 6자 이상이어야 합니다.", prefill)); return
        if pw != pw2:
            self._html(page_signup(None, "비밀번호가 일치하지 않습니다.", prefill)); return
        if not name:
            self._html(page_signup(None, "이름을 입력하세요.", prefill)); return

        users = load_users()
        if uid in users:
            self._html(page_signup(None, f"'{uid}' 아이디는 이미 사용 중입니다.", prefill)); return

        users[uid] = {
            "pw":     hash_pw(pw),
            "name":   name,
            "email":  email,
            "phone":  phone,
            "area":   area,
            "joined": datetime.now().strftime("%Y-%m-%d"),
        }
        save_users(users)
        tok = new_session(uid, name, email)
        self._redirect("/mypage", cookie=tok)


# ═══════════════════════════════════════════════════════════════
# 12. 메인
# ═══════════════════════════════════════════════════════════════
def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    _ensure()
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"🎾 김포 테니스 대시보드 시작: http://localhost:{port}")
    print("   종료: Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버 종료")

if __name__ == "__main__":
    main()
