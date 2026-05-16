$extens("include.py")
include("import requests", ["extella-pip install requests"])
include("import pycookiecheat", ["extella-pip install pycookiecheat"])
include("import installed_browsers", ["extella-pip install installed-browsers"])

OAUTH_CALLBACK_PORTS = [8891, 8892, 8893, 8894, 8895]


def meta_app_onboarding_assistant(
    api_token: str = "",
    base_url: str = "https://api.extella.ai",
    meta_app_id: str = "",
    meta_app_secret: str = "",
    open_browser: bool = True,
) -> dict:
    import re
    import subprocess
    import platform
    import requests

    def extella_headers():
        return {
            "X-Auth-Token": api_token,
            "Content-Type": "application/json",
            "X-Profile-Id": "default",
            "X-Agent-Id": "agent_extella_default",
        }

    def kv_get(key: str) -> str:
        try:
            r = requests.post(
                f"{base_url}/api/kv/get",
                headers=extella_headers(),
                json={"key": key},
                timeout=15,
            )
            return (r.json() or {}).get("value") or ""
        except Exception:
            return ""

    def kv_set(key: str, value: str, description: str) -> bool:
        try:
            r = requests.post(
                f"{base_url}/api/kv/set",
                headers=extella_headers(),
                json={"key": key, "value": value, "description": description},
                timeout=15,
            )
            js = r.json() if r.content else {}
            return r.ok and not js.get("error") and js.get("status") != "error"
        except Exception:
            return False

    redirect_uris = []
    for port in OAUTH_CALLBACK_PORTS:
        redirect_uris.append(f"http://localhost:{port}/callback")
        redirect_uris.append(f"http://127.0.0.1:{port}/callback")
    redirect_block = "\n".join(redirect_uris)

    links = {
        "create_or_manage_apps": "https://developers.facebook.com/apps/",
        "facebook_login_docs": "https://developers.facebook.com/docs/facebook-login/",
        "marketing_api_docs": "https://developers.facebook.com/docs/marketing-api/",
    }

    print("[1/3] Detecting browser and Facebook login (optional UX check)...")

    try:
        import installed_browsers

        default_browser = installed_browsers.what_is_the_default_browser() or "Unknown"
    except Exception:
        default_browser = "Unknown"

    try:
        from pycookiecheat import BrowserType, get_cookies
    except ImportError as e:
        return {
            "status": "error",
            "message": f"pycookiecheat not available: {e}. Run: extella-pip install pycookiecheat",
            "redirect_uris_to_register": redirect_uris,
            "redirect_uris_copy_block": redirect_block,
            "links": links,
        }

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

    facebook_logged_in = bool(cookies.get("c_user"))
    print(f"[1/3] Default browser: {default_browser}; Facebook cookie session: {facebook_logged_in}")

    existing_id = kv_get("meta_app_id")
    existing_secret = kv_get("meta_app_secret")
    kv_already_configured = bool(existing_id and existing_secret)

    if open_browser:
        print("[2/3] Opening Meta for Developers in the system browser...")
        try:
            sys_platform = platform.system()
            target_url = links["create_or_manage_apps"]
            if sys_platform == "Darwin":
                subprocess.run(["open", target_url], check=False)
            elif sys_platform == "Windows":
                subprocess.run(["start", "", target_url], shell=True, check=False)
            else:
                subprocess.run(["xdg-open", target_url], check=False)
        except Exception as e:
            print(f"[2/3] Could not open browser automatically: {e}")

    app_id_in = (meta_app_id or "").strip()
    secret_in = (meta_app_secret or "").strip()

    if not app_id_in or not secret_in:
        next_action = (
            "Create a Meta Developer app at developers.facebook.com, then add every URI from "
            "`redirect_uris_copy_block` under Valid OAuth Redirect URIs. Re-run this expert with "
            "`meta_app_id` and `meta_app_secret` to validate and save to KV."
        )
        return {
            "status": "awaiting_app_credentials",
            "facebook_logged_in": facebook_logged_in,
            "browser_used": browser_used,
            "default_browser_reported": default_browser,
            "kv_already_configured": kv_already_configured,
            "existing_meta_app_id_set": bool(existing_id),
            "next_action": next_action,
            "redirect_uris_to_register": redirect_uris,
            "redirect_uris_copy_block": redirect_block,
            "oauth_scopes_preset_uses": "ads_management,ads_read,business_management",
            "links": links,
            "kv_saved": False,
        }

    print("[3/3] Validating App ID / Secret via Graph API and saving to KV...")

    if not re.fullmatch(r"\d{5,20}", app_id_in):
        return {
            "status": "error",
            "message": "meta_app_id should be a numeric App ID (digits only, typical length 15–17).",
            "facebook_logged_in": facebook_logged_in,
            "browser_used": browser_used,
            "redirect_uris_to_register": redirect_uris,
            "redirect_uris_copy_block": redirect_block,
            "links": links,
            "kv_saved": False,
        }

    if len(secret_in) < 8:
        return {
            "status": "error",
            "message": "meta_app_secret looks too short. Copy the full App Secret from Settings → Basic.",
            "facebook_logged_in": facebook_logged_in,
            "browser_used": browser_used,
            "redirect_uris_to_register": redirect_uris,
            "redirect_uris_copy_block": redirect_block,
            "links": links,
            "kv_saved": False,
        }

    app_token = f"{app_id_in}|{secret_in}"
    try:
        r = requests.get(
            f"https://graph.facebook.com/v25.0/{app_id_in}",
            params={"fields": "id,name", "access_token": app_token},
            timeout=20,
        )
        info = r.json()
        if "error" in info:
            err = info["error"]
            return {
                "status": "error",
                "message": f"Graph API rejected app credentials: {err.get('message', err)}",
                "facebook_logged_in": facebook_logged_in,
                "browser_used": browser_used,
                "redirect_uris_to_register": redirect_uris,
                "redirect_uris_copy_block": redirect_block,
                "links": links,
                "kv_saved": False,
            }
        app_name = info.get("name", "")
    except Exception as e:
        return {
            "status": "error",
            "message": f"Could not reach Meta Graph API: {e}",
            "facebook_logged_in": facebook_logged_in,
            "browser_used": browser_used,
            "redirect_uris_to_register": redirect_uris,
            "redirect_uris_copy_block": redirect_block,
            "links": links,
            "kv_saved": False,
        }

    ok_id = kv_set("meta_app_id", app_id_in, "Meta Developer App ID (OAuth client_id) for pixel installer")
    ok_sec = kv_set("meta_app_secret", secret_in, "Meta Developer App Secret (OAuth client_secret) for pixel installer")
    kv_saved = ok_id and ok_sec

    if not kv_saved:
        return {
            "status": "error",
            "message": "Credentials validated with Meta, but KV Store save failed. Check api_token and Extella API access.",
            "facebook_logged_in": facebook_logged_in,
            "browser_used": browser_used,
            "app_id_verified": app_id_in,
            "app_name": app_name,
            "redirect_uris_to_register": redirect_uris,
            "redirect_uris_copy_block": redirect_block,
            "links": links,
            "kv_saved": False,
        }

    return {
        "status": "success",
        "message": "Meta App ID and App Secret validated and saved to KV. You can run meta_token_from_browser next.",
        "facebook_logged_in": facebook_logged_in,
        "browser_used": browser_used,
        "app_id_verified": app_id_in,
        "app_name": app_name,
        "redirect_uris_to_register": redirect_uris,
        "redirect_uris_copy_block": redirect_block,
        "links": links,
        "kv_saved": True,
    }
