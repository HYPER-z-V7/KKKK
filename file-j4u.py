# -*- coding: utf-8 -*-
"""rihanx_speed_patch.py — boot speed, I/O debounce, gzip, Render hardening."""
import os, shutil, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
ok = miss = 0

def sub(old, new, path="main.py", required=True):
    global ok, miss
    p = ROOT / path
    if not p.exists():
        miss += 1; return
    t = p.read_text(encoding="utf-8")
    if old not in t:
        if required: print(f"  ! not found: {old[:70]!r}")
        miss += 1; return
    if not p.with_suffix(p.suffix + ".bak").exists():
        shutil.copy2(p, p.with_suffix(p.suffix + ".bak"))
    p.write_text(t.replace(old, new, 1), encoding="utf-8")
    ok += 1

print("[1/6] paths + env tuning")
sub('''WEB_HOST = "0.0.0.0"
WEB_PORT = int(os.environ.get("PORT", 8080))
ACCOUNTS_FILE = "accounts.json"
TOKEN_CACHE_FILE = "token_cache.json"
DEVICES_FILE = "devices.json"
PANEL_DB_FILE = "panel_db.json"
TOKEN_CACHE_TTL = 1200''',
'''WEB_HOST = "0.0.0.0"
WEB_PORT = int(os.environ.get("PORT", 8080))
DATA_DIR = os.environ.get("DATA_DIR", ".").strip() or "."
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except Exception:
    DATA_DIR = "."
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")
TOKEN_CACHE_FILE = os.path.join(DATA_DIR, "token_cache.json")
DEVICES_FILE = os.path.join(DATA_DIR, "devices.json")
PANEL_DB_FILE = os.path.join(DATA_DIR, "panel_db.json")
TOKEN_CACHE_TTL = 1200''')

sub("START_MATCH_INTERVAL = 5.0", 'START_MATCH_INTERVAL = float(os.environ.get("START_MATCH_INTERVAL", "3.0"))')
sub("NEW_MATCH_DELAY = 1.0", 'NEW_MATCH_DELAY = float(os.environ.get("NEW_MATCH_DELAY", "0.4"))')
sub("MATCH_IDLE_TIMEOUT  = 45.0", 'MATCH_IDLE_TIMEOUT  = float(os.environ.get("MATCH_IDLE_TIMEOUT", "45"))')
sub("MOVEMENT_TICK_MS            = 240", 'MOVEMENT_TICK_MS            = int(os.environ.get("MOVEMENT_TICK_MS", "240"))')
sub("TEAM_INVITE_WAIT = 2.5", 'TEAM_INVITE_WAIT = float(os.environ.get("TEAM_INVITE_WAIT", "1.6"))')
sub("TEAM_READY_DELAY = 6.0", 'TEAM_READY_DELAY = float(os.environ.get("TEAM_READY_DELAY", "3.5"))')
sub("_LOGIN_SEMAPHORE = asyncio.Semaphore(4)",
    '_LOGIN_CONCURRENCY = int(os.environ.get("LOGIN_CONCURRENCY", "8"))\n_LOGIN_SEMAPHORE = asyncio.Semaphore(_LOGIN_CONCURRENCY)')

print("[2/6] accounts.json mtime cache")
sub('''def get_account_index_for_uid(uid_str: str, account_data: dict = None) -> int:''',
'''_UID_CACHE = {"mtime": -1.0, "uids": []}


def _accounts_uids() -> list:
    try:
        m = os.path.getmtime(ACCOUNTS_FILE)
    except OSError:
        return []
    if m != _UID_CACHE["mtime"]:
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                accs = json.load(f)
            _UID_CACHE["uids"] = [str(a.get("uid", "")) for a in accs if isinstance(a, dict)]
            _UID_CACHE["mtime"] = m
        except Exception:
            return _UID_CACHE["uids"]
    return _UID_CACHE["uids"]


def get_account_index_for_uid(uid_str: str, account_data: dict = None) -> int:''')

sub('''    try:
        if os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                accs = json.load(f)
            uids = [str(a.get("uid", "")) for a in accs if isinstance(a, dict)]
            for tu in target_uids:
                if tu in uids:
                    return uids.index(tu)
    except Exception:
        pass
    return 0''',
'''    uids = _accounts_uids()
    for tu in target_uids:
        if tu in uids:
            return uids.index(tu)
    return 0''')

sub('''    partner_auth_uid = ""
    try:
        if os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                accs = json.load(f)
            if 0 <= partner_idx < len(accs):
                partner_auth_uid = str(accs[partner_idx].get("uid", ""))
    except Exception:
        pass
    return partner_idx, partner_auth_uid''',
'''    uids = _accounts_uids()
    partner_auth_uid = uids[partner_idx] if 0 <= partner_idx < len(uids) else ""
    return partner_idx, partner_auth_uid''')

print("[3/6] panel DB write debounce")
sub('''        self.settings = {''', '''        self._dirty = False
        self.settings = {''')
sub('''    def save(self):
        try:
            with open(PANEL_DB_FILE, "w", encoding="utf-8") as f:
                json.dump({''',
'''    def save(self):
        self._dirty = True

    def save_now(self):
        self._dirty = False
        try:
            with open(PANEL_DB_FILE, "w", encoding="utf-8") as f:
                json.dump({''')

print("[4/6] static cache + gzip")
sub('''async def serve_html_file(filename: str):
    path = _find_file(filename)
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return aiohttp.web.Response(text=f.read(), content_type="text/html", charset="utf-8")
    return aiohttp.web.Response(text=f"<h1>{filename} not found</h1>", content_type="text/html", status=404)''',
'''_FILE_CACHE: Dict[str, Tuple[float, str]] = {}


def _read_text(path: str) -> str:
    try:
        m = os.path.getmtime(path)
    except OSError:
        return ""
    hit = _FILE_CACHE.get(path)
    if hit and hit[0] == m:
        return hit[1]
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = f.read()
    except Exception:
        return ""
    _FILE_CACHE[path] = (m, data)
    return data


def _cached_resp(path: str, ctype: str, cache_secs: int = 300):
    body = _read_text(path)
    if not body:
        return aiohttp.web.Response(text="", content_type=ctype)
    resp = aiohttp.web.Response(text=body, content_type=ctype, charset="utf-8")
    resp.headers["Cache-Control"] = f"public, max-age={cache_secs}"
    resp.enable_compression()
    return resp


async def serve_html_file(filename: str):
    path = _find_file(filename)
    if path:
        return _cached_resp(path, "text/html", 60)
    return aiohttp.web.Response(text=f"<h1>{filename} not found</h1>", content_type="text/html", status=404)''')

sub('''    path = _find_file("shared.js")
    content = ""
    if path:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    return aiohttp.web.Response(text=content + "\\n" + _SHARED_JS_EXTRAS, content_type="application/javascript", charset="utf-8")''',
'''    path = _find_file("shared.js")
    content = _read_text(path) if path else ""
    resp = aiohttp.web.Response(text=content + "\\n" + _SHARED_JS_EXTRAS,
                                content_type="application/javascript", charset="utf-8")
    resp.headers["Cache-Control"] = "public, max-age=300"
    resp.enable_compression()
    return resp''')

sub('''    path = _find_file("shared.css")
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return aiohttp.web.Response(text=f.read(), content_type="text/css", charset="utf-8")
    return aiohttp.web.Response(text="", content_type="text/css")''',
'''    path = _find_file("shared.css")
    if path:
        return _cached_resp(path, "text/css", 600)
    return aiohttp.web.Response(text="", content_type="text/css")''')

print("[5/6] light stats + workers")
sub('async def api_stats(request):',
'''async def api_stats_light(request):
    accs = list(bot_state.accounts.values())
    return aiohttp.web.json_response({
        "online": sum(1 for a in accs if a.get("status") in ("ONLINE", "IN_MATCH", "SEARCHING")),
        "accounts": len(accs),
        "matches": bot_state.matches_started,
        "exp": bot_state.total_exp_gained,
        "uptime": int(time.time() - bot_state.start_time),
        "creating": bool(bot_state.creating),
    })


async def api_stats(request):''')

sub('async def handle_healthz(request):',
'''async def panel_flush_worker():
    while True:
        try:
            await asyncio.sleep(3.0)
            if getattr(panel_db, "_dirty", False):
                panel_db.save_now()
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(5)


async def render_keepalive_worker():
    base = (os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("KEEPALIVE_URL") or "").strip()
    if not base:
        return
    url = base.rstrip("/") + "/healthz"
    await asyncio.sleep(45)
    while True:
        try:
            await client.get(url, timeout=10)
        except Exception:
            pass
        await asyncio.sleep(600)


async def handle_healthz(request):''')

sub('    app.router.add_get("/api/stats", api_stats)',
    '    app.router.add_get("/api/stats", api_stats)\n    app.router.add_get("/api/stats/light", api_stats_light)')

print("[6/6] boot wiring + SIGTERM")
sub('''    asyncio.create_task(supervisor_worker())''',
'''    asyncio.create_task(supervisor_worker())
    asyncio.create_task(panel_flush_worker())
    asyncio.create_task(render_keepalive_worker())

    def _on_term():
        print_warning("[SIGTERM] graceful shutdown")
        try: panel_db.save_now()
        except Exception: pass
        for t in list(bot_state.account_workers.values()):
            try: t.cancel()
            except Exception: pass

    try:
        import signal as _sig
        _loop = asyncio.get_running_loop()
        for _s in (_sig.SIGTERM, _sig.SIGINT):
            try: _loop.add_signal_handler(_s, _on_term)
            except Exception: pass
    except Exception:
        pass''')

sub('            await asyncio.sleep(0.5)\\n        except Exception as e:\\n            print_error(f"[BOOT] Record {i} failed validation',
    '            await asyncio.sleep(0.06)\\n        except Exception as e:\\n            print_error(f"[BOOT] Record {i} failed validation')

p = ROOT / "main.py"
if p.exists():
    t = p.read_text(encoding="utf-8")
    if "def _seed_data_dir" not in t:
        t = t.replace('''async def _autoload_accounts():''',
'''def _seed_data_dir():
    if os.path.abspath(DATA_DIR) == os.path.abspath("."):
        return
    for name in ("accounts.json", "panel_db.json", "devices.json"):
        src = os.path.join(".", name)
        dst = os.path.join(DATA_DIR, name)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
                print_info(f"[BOOT] seeded {name} -> {DATA_DIR}")
            except Exception:
                pass


async def _autoload_accounts():''', 1)
        t = t.replace("    try:\\n        await _autoload_accounts()",
                      "    _seed_data_dir()\\n    try:\\n        await _autoload_accounts()", 1)
        t = t.replace("import sys, os, json, time, uuid, random, asyncio, base64, struct, socket",
                      "import sys, os, json, time, uuid, random, asyncio, base64, struct, socket, shutil", 1)
        p.write_text(t, encoding="utf-8"); ok += 2

print(f"\\nDone. patches={ok} missing={miss}")