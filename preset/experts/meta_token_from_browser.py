$extens("include.py")
include("import requests", ["extella-pip install requests"])
include("import pycookiecheat", ["extella-pip install pycookiecheat"])
include("import installed_browsers", ["extella-pip install installed-browsers"])

def meta_token_from_browser(
    api_token: str = "",
    base_url: str = "https://api.extella.ai",
    callback_port: int = 8891,
    oauth_timeout: int = 120,
) -> dict:
    import requests
    import time
    import json
    import threading
    import subprocess
    import platform
    import http.server
    import urllib.parse
    import socket

    print("[1/5] Detecting browser and checking Facebook login...")

    def _kv_headers():
        return {
            "X-Auth-Token": api_token,
            "Content-Type": "application/json",
            "X-Profile-Id": "default",
            "X-Agent-Id": "agent_extella_default",
        }

    # --- Get credentials from KV Store ---
    def kv_get(key):
        try:
            r = requests.post(f"{base_url}/api/kv/get",
                headers=_kv_headers(),
                json={"key": key}, timeout=10)
            return r.json().get("value", "")
        except:
            return ""

    meta_app_id = kv_get("meta_app_id")
    meta_app_secret = kv_get("meta_app_secret")

    if not meta_app_id or not meta_app_secret:
        return {
            "status": "error",
            "message": (
                "meta_app_id and meta_app_secret not found in KV Store. "
                "Run the local expert meta_app_onboarding_assistant (see concept 12_meta_developer_app_onboarding) "
                "or set both keys manually in KV."
            ),
            "action_required": "meta_app_onboarding_assistant → KV keys meta_app_id, meta_app_secret",
        }

    # --- Detect default browser ---
    try:
        import installed_browsers
        default_browser = installed_browsers.what_is_the_default_browser() or "Unknown"
    except Exception:
        default_browser = "Unknown"

    print(f"[1/5] Default browser: {default_browser}")

    # --- Read Facebook cookies ---
    try:
        from pycookiecheat import BrowserType, get_cookies
    except ImportError as e:
        return {"status": "error", "message": f"pycookiecheat not available: {e}. Run: extella-pip install pycookiecheat"}

    BROWSER_MAP = {
        "Google Chrome": BrowserType.CHROME,
        "Chrome": BrowserType.CHROME,
        "Mozilla Firefox": BrowserType.FIREFOX,
        "Firefox": BrowserType.FIREFOX,
        "Safari": BrowserType.SAFARI,
        "Brave Browser": BrowserType.BRAVE,
        "Brave": BrowserType.BRAVE,
        "Microsoft Edge": BrowserType.EDGE,
        "Edge": BrowserType.EDGE,
    }

    fallback_browsers = [
        (default_browser, BROWSER_MAP.get(default_browser, BrowserType.CHROME)),
        ("Firefox", BrowserType.FIREFOX),
        ("Safari", BrowserType.SAFARI),
        ("Chrome", BrowserType.CHROME),
    ]

    cookies = {}
    browser_used = default_browser
    for name, btype in fallback_browsers:
        try:
            cookies = get_cookies("https://www.facebook.com", browser=btype)
            if cookies:
                browser_used = name
                break
        except Exception:
            continue

    is_logged_in = bool(cookies.get("c_user"))
    print(f"[1/5] Facebook login detected: {is_logged_in} (browser: {browser_used})")

    if not is_logged_in:
        return {
            "status": "not_logged_in",
            "browser_used": browser_used,
            "message": "Not logged into Facebook in the default browser. Please log in at facebook.com and try again, or provide your Meta access token manually.",
        }

    print("[2/5] Starting OAuth callback server...")

    # --- Find available port ---
    port = callback_port
    for p in [callback_port, 8892, 8893, 8894, 8895]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", p))
            port = p
            break
        except OSError:
            continue

    # --- OAuth callback server ---
    class _OAuthHandler(http.server.BaseHTTPRequestHandler):
        result = {}

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if "/callback" in parsed.path:
                params = urllib.parse.parse_qs(parsed.query)
                _OAuthHandler.result["code"] = params.get("code", [None])[0]
                _OAuthHandler.result["error"] = params.get("error", [None])[0]
                body = (
                    b"<html><body style='font-family:sans-serif;text-align:center;padding:60px'>"
                    b"<h2 style='color:#1877f2'>Authorization Successful!</h2>"
                    b"<p>You can close this tab and return to the chat.</p>"
                    b"</body></html>"
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                threading.Thread(target=self.server.shutdown, daemon=True).start()

        def log_message(self, *a):
            pass

    _OAuthHandler.result = {}
    server = http.server.HTTPServer(("127.0.0.1", port), _OAuthHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # --- Build OAuth URL and open browser ---
    print("[3/5] Opening OAuth dialog in browser...")
    redirect_uri = f"http://localhost:{port}/callback"
    params = {
        "client_id": meta_app_id,
        "redirect_uri": redirect_uri,
        "scope": "ads_management,ads_read,business_management",
        "response_type": "code",
        "state": "extella_pixel_installer",
    }
    oauth_url = "https://www.facebook.com/dialog/oauth?" + urllib.parse.urlencode(params)

    try:
        sys_platform = platform.system()
        if sys_platform == "Darwin":
            subprocess.run(["open", oauth_url], check=False)
        elif sys_platform == "Windows":
            subprocess.run(["start", "", oauth_url], shell=True, check=False)
        else:
            subprocess.run(["xdg-open", oauth_url], check=False)
    except Exception as e:
        return {"status": "error", "message": f"Could not open browser: {e}. Open this URL manually: {oauth_url}"}

    print(f"[3/5] OAuth dialog opened. Waiting for authorization (timeout: {oauth_timeout}s)...")

    # --- Wait for OAuth code ---
    deadline = time.time() + oauth_timeout
    while time.time() < deadline:
        code = _OAuthHandler.result.get("code")
        error = _OAuthHandler.result.get("error")
        if code or error:
            break
        time.sleep(1)

    code = _OAuthHandler.result.get("code")
    oauth_error = _OAuthHandler.result.get("error")

    if oauth_error:
        return {"status": "error", "message": f"OAuth denied: {oauth_error}"}
    if not code:
        return {"status": "error", "message": f"OAuth timeout after {oauth_timeout}s. Please try again."}

    print("[4/5] Exchanging authorization code for access token...")

    # --- Exchange code for short-lived token ---
    try:
        r = requests.get("https://graph.facebook.com/v25.0/oauth/access_token", params={
            "client_id": meta_app_id,
            "client_secret": meta_app_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        }, timeout=30)
        r.raise_for_status()
        short_token = r.json().get("access_token")
        if not short_token:
            return {"status": "error", "message": f"Token exchange failed: {r.json()}"}
    except Exception as e:
        return {"status": "error", "message": f"Token exchange failed: {e}"}

    # --- Exchange for long-lived token (60 days) ---
    try:
        r2 = requests.get("https://graph.facebook.com/v25.0/oauth/access_token", params={
            "grant_type": "fb_exchange_token",
            "client_id": meta_app_id,
            "client_secret": meta_app_secret,
            "fb_exchange_token": short_token,
        }, timeout=30)
        r2.raise_for_status()
        long_token = r2.json().get("access_token", short_token)
    except Exception:
        long_token = short_token  # fall back to short-lived token

    # --- Get user info and ad accounts ---
    print("[5/5] Getting ad accounts...")
    try:
        me = requests.get("https://graph.facebook.com/v25.0/me",
            params={"fields": "id,name", "access_token": long_token}, timeout=15).json()
        user_name = me.get("name", "Unknown")

        accounts_resp = requests.get("https://graph.facebook.com/v25.0/me/adaccounts",
            params={"fields": "id,name,account_status", "access_token": long_token,
                    "limit": 50}, timeout=15).json()
        ad_accounts = [
            {"id": a["id"], "name": a.get("name", ""), "status": a.get("account_status", 0)}
            for a in accounts_resp.get("data", [])
        ]
    except Exception as e:
        return {"status": "error", "message": f"Could not get ad accounts: {e}"}

    # --- Save token to KV Store ---
    try:
        requests.post(f"{base_url}/api/kv/set",
            headers=_kv_headers(),
            json={"key": "meta_access_token", "value": long_token,
                  "description": f"Meta access token for {user_name}"}, timeout=10)
    except Exception:
        pass  # non-fatal

    print("[5/5] Done! Token obtained and saved.")

    return {
        "status": "success",
        "token": long_token,
        "user_name": user_name,
        "ad_accounts": ad_accounts,
        "browser_used": browser_used,
        "token_saved_to_kv": "meta_access_token",
    }
