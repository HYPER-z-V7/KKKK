# -*- coding: utf-8 -*-
"""
rihanx_patch.py — RIHAN X branding + stability patch for GLORY-BOT
Runs automatically at build time. Safe to re-run (skips applied patches).
"""
import os, shutil, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
ok, miss = 0, 0

def sub(path, old, new, required=True):
    global ok, miss
    p = ROOT / path
    if not p.exists():
        if required: print(f"  ! missing file: {path}")
        miss += 1; return
    txt = p.read_text(encoding="utf-8")
    if old not in txt:
        if required: print(f"  ! not found in {path}: {old[:60]!r}")
        miss += 1; return
    if not (ROOT / (path + ".bak")).exists():
        shutil.copy2(p, p.with_suffix(p.suffix + ".bak"))
    p.write_text(txt.replace(old, new), encoding="utf-8")
    ok += 1

print("[1/4] core branding")
sub("main.py", "#   main.py — DG DRIFT / FFGLORY COMPLETE SERVER + 2-BOT DUO ENGINE",
               "#   main.py — RIHAN X COMPLETE SERVER + 2-BOT DUO ENGINE")
sub("main.py", '("dgdrift_salt_" + str(pw))', '("rihanx_salt_" + str(pw))')
sub("main.py", '''        if "admin" not in self.users:
            self.users["admin"] = {
                "username": "admin",
                "display_name": "Admin",
                "password_hash": _hash_pw("admin123"),''',
'''        if "rihanx" not in self.users:
            self.users["rihanx"] = {
                "username": "rihanx",
                "display_name": "RIHAN X OWNER",
                "password_hash": _hash_pw("RihanX@999"),''')
sub("main.py", '''            "discord": "https://discord.gg/uFFd8c7B5A",
            "support": "https://discord.gg/uFFd8c7B5A",''',
'''            "discord": "https://discord.gg/rihanx",
            "support": "https://discord.gg/rihanx",''')
sub("main.py", 'nickname_final = f"DISHA-{rand_num}"', 'nickname_final = f"RIHANX-{rand_num}"')
sub("main.py", 'panel_db.settings.get("telegram", "https://t.me/dg_drift")',
               'panel_db.settings.get("telegram", "https://t.me/rihanx")')
sub("main.py", '"SINGH"', '"RIHANX"', required=False)

print("[2/4] stability fixes")
sub("main.py", "MAX_CONCURRENT_MATCHES = 20",
               'MAX_CONCURRENT_MATCHES = int(os.environ.get("MAX_CONCURRENT_MATCHES", "20"))')
sub("main.py", '''async def handle_root(request):
    # The main page opens index.html only.
    return await serve_html_file("index.html")''',
'''async def handle_root(request):
    # Public landing page; bot dashboard lives at /bot
    return await serve_html_file("ffglory.html")''')
sub("main.py", '''    for cand in (
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "logo.gif"),''',
'''    for cand in (
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "logo.svg"),
        os.path.join("static", "logo.svg"),''')
sub("main.py", '"version": "2.0"', '"version": "3.0"')

print("[3/4] healthcheck + admin settings + supervisor")
sub("main.py", "# ==================== CLIENT API (client.html) ====================",
'''async def api_admin_settings_get(request):
    _, err = _require_admin(request)
    if err: return err
    return aiohttp.web.json_response(panel_db.settings)

async def api_admin_settings_set(request):
    _, err = _require_admin(request)
    if err: return err
    body = await request.json()
    for k in ("basic_credit_usd", "premium_credit_usd", "binance_pay_id",
              "discord", "support", "telegram", "whatsapp"):
        if k in body:
            panel_db.settings[k] = body[k]
    panel_db.save()
    return aiohttp.web.json_response({"ok": True})


# ==================== CLIENT API (client.html) ====================''')

sub("main.py", "async def start_web_server():",
'''async def handle_healthz(request):
    return aiohttp.web.json_response({
        "ok": True, "app": "RIHAN X", "uptime": int(time.time() - bot_state.start_time),
        "bots": len(bot_state.accounts),
    })


async def supervisor_worker():
    """Revive dead account workers so glory farming never stalls."""
    while True:
        try:
            await asyncio.sleep(20)
            if bot_state.creating:
                continue
            for uid, task in list(bot_state.account_workers.items()):
                if task is None or task.done():
                    bot_state.account_workers.pop(uid, None)
            if not os.path.exists(ACCOUNTS_FILE):
                continue
            try:
                with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                    accs = json.load(f)
            except Exception:
                continue
            if not isinstance(accs, list):
                continue
            running = set(bot_state.account_workers.keys())
            for a in accs:
                if not isinstance(a, dict):
                    continue
                u = str(a.get("uid", "")).strip()
                p = str(a.get("password", "")).strip()
                if not u or not p or u in running or bot_state.is_paused(u):
                    continue
                print_warning(f"[SUPERVISOR] reviving worker {u}")
                bot_state.account_workers[u] = asyncio.create_task(
                    account_loop_guest(u, p, region_override=a.get("region"),
                                       clan_override=a.get("clan_id")))
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print_error(f"[SUPERVISOR] {e}")
            await asyncio.sleep(10)


async def start_web_server():''')

sub("main.py", '    app.router.add_get("/", handle_root)',
               '    app.router.add_get("/", handle_root)\n    app.router.add_get("/healthz", handle_healthz)')
sub("main.py", '    app.router.add_post("/api/admin/join-clan", api_admin_join_clan)',
'''    app.router.add_post("/api/admin/join-clan", api_admin_join_clan)
    app.router.add_get("/api/admin/settings", api_admin_settings_get)
    app.router.add_post("/api/admin/settings", api_admin_settings_set)''')

sub("main.py", '''    try:
        await _autoload_accounts()
    except Exception as e:
        print_error(f"[BOOT] autoload failed: {e}")''',
'''    try:
        await _autoload_accounts()
    except Exception as e:
        print_error(f"[BOOT] autoload failed: {e}")

    asyncio.create_task(supervisor_worker())''')

print("[4/4] global text rebrand")
targets = ["main.py", "README.md", "templates/index.html", "templates/ffglory.html",
           "templates/login.html", "templates/client.html", "templates/admin.html",
           "templates/shared.js", "templates/shared.css", "static/logo.svg"]
pairs = [("ISHU X 999", "RIHAN X"), ("ISHU X999", "RIHAN X"), ("DG DRIFT", "RIHAN X"),
         ("DISHA X ISHU", "RIHAN X"), ("dg_drift", "rihanx")]
for f in targets:
    p = ROOT / f
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8"); orig = t
    for a, b in pairs:
        t = t.replace(a, b)
    if t != orig:
        p.write_text(t, encoding="utf-8"); ok += 1

for stale in ("panel_db.json", "token_cache.json"):
    if (ROOT / stale).exists():
        os.remove(ROOT / stale); print(f"  removed stale {stale}")

print(f"\nDone. patches={ok} missing={miss}")