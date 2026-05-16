"""
bootstrap.py — Publishes the Meta Pixel Installer preset to Extella API.
Publishes all concepts under preset/concepts/ and all experts in EXPERT_META.

Usage:
    python3 bootstrap.py
    python3 bootstrap.py --dry-run                 # print only, no API calls
    python3 bootstrap.py --sync-concept-registry   # fill preset/concept_registry.json from /api/concept/list (match by first ## heading), then exit

Concept updates:
    If preset/concept_registry.json maps a file path to concept_id, POST /api/concept/update is used.
    Otherwise POST /api/concept/add runs and the new id is written to the registry.

    If concepts were published before the registry existed, run once with --sync-concept-registry
    to map remote concept_ids by matching the first markdown heading (## ...) of each local file.
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

# ─── Config ──────────────────────────────────────────────────────────────────

API_TOKEN = os.environ.get("EXTELLA_TOKEN", "")
BASE_URL  = os.environ.get("EXTELLA_URL", "https://api.extella.ai")
DRY_RUN   = "--dry-run" in sys.argv
SYNC_ONLY = "--sync-concept-registry" in sys.argv

PRESET_DIR = Path(__file__).parent / "preset"
CONCEPTS_DIR = PRESET_DIR / "concepts"
EXPERTS_DIR  = PRESET_DIR / "experts"
CONCEPT_REGISTRY_PATH = PRESET_DIR / "concept_registry.json"

HEADERS = {
    "X-Auth-Token": API_TOKEN,
    "Content-Type": "application/json",
    "X-Profile-Id": "default",
    "X-Agent-Id": "agent_extella_default",
}

# ─── Concept registry (update vs add) ───────────────────────────────────────

def load_concept_registry():
    if not CONCEPT_REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(CONCEPT_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_concept_registry(reg: dict):
    CONCEPT_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONCEPT_REGISTRY_PATH.write_text(
        json.dumps(reg, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def first_concept_heading_line(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("##"):
            return s[:320]
    return ""


def flatten_concept_list(payload) -> list:
    if not isinstance(payload, dict):
        return []
    for key in ("concepts", "results", "data", "items", "list"):
        v = payload.get(key)
        if isinstance(v, list):
            return v
    return []


def concept_item_id(item: dict):
    for k in ("concept_id", "id", "conceptId"):
        v = item.get(k)
        if v is not None and str(v).isdigit():
            return int(v)
    return None


def concept_item_text(item: dict) -> str:
    return item.get("text") or item.get("concept_text") or item.get("new_text") or ""


# ─── Helpers ─────────────────────────────────────────────────────────────────

def api_post(path, payload):
    if DRY_RUN:
        print(f"  [DRY-RUN] POST {path}")
        return {"status": "success", "id": 0, "expert_name": payload.get("name", "")}
    resp = requests.post(f"{BASE_URL}{path}", headers=HEADERS, json=payload, timeout=30)
    return resp.json()

def read_file(path):
    return Path(path).read_text(encoding="utf-8")

def color(text, code):
    return f"\033[{code}m{text}\033[0m"

OK  = color("✓", "32")
ERR = color("✗", "31")
INF = color("→", "36")


def sync_concept_registry_from_remote():
    """Match local concept files to remote concepts by first ## heading line; write concept_registry.json."""
    print(f"\n{color('SYNC CONCEPT REGISTRY', '1;36')}  ←  POST /api/concept/list\n")

    data = api_post("/api/concept/list", {})
    items = flatten_concept_list(data)
    if not items:
        print(f"{ERR} No concepts in API response or unexpected shape: {str(data)[:500]}")
        return False

    reg = {}
    matched = 0
    ambiguous = 0

    for cf in sorted(CONCEPTS_DIR.glob("*.txt")):
        rel_key = str(cf.relative_to(PRESET_DIR))
        local_text = read_file(cf)
        fp = first_concept_heading_line(local_text)
        if not fp:
            print(f"{ERR} {rel_key}: no ## heading — cannot fingerprint")
            continue

        hits = []
        for it in items:
            if not isinstance(it, dict):
                continue
            remote_text = concept_item_text(it)
            rp = first_concept_heading_line(remote_text)
            if fp == rp and fp:
                cid = concept_item_id(it)
                if cid is not None:
                    hits.append((cid, it))

        if not hits:
            print(f"{INF} {rel_key}: no remote match for heading {fp[:60]}...")
            continue
        hits.sort(key=lambda x: x[0], reverse=True)
        best_id = hits[0][0]
        if len(hits) > 1:
            ambiguous += 1
            print(f"{INF} {rel_key}: multiple matches ({len(hits)}), using highest concept_id={best_id}")

        reg[rel_key] = best_id
        matched += 1
        print(f"  {OK} {rel_key} → concept_id {best_id}")

    if matched == 0:
        print(f"\n{ERR} No matches — registry not written. Check API response shape or remote concepts.")
        return False

    save_concept_registry(reg)
    print(f"\n{color(f'Matched {matched} files; wrote {CONCEPT_REGISTRY_PATH}', '32')}")
    if ambiguous:
        print(f"{color(f'Note: {ambiguous} files had multiple remote matches (used newest id).', '33')}")
    return matched > 0

# ─── Expert Metadata ─────────────────────────────────────────────────────────

EXPERT_META = {
    "meta_app_onboarding_assistant": {
        "name": "meta_app_onboarding_assistant",
        "description": (
            "Guided onboarding for Meta (Facebook) Developer App credentials used by the pixel installer OAuth flow. "
            "Runs LOCALLY (target=device_uuid). Detects default browser, checks Facebook login via cookies, "
            "optionally opens developers.facebook.com, returns exact Valid OAuth Redirect URIs to paste in Meta, "
            "and the scopes this preset uses. When meta_app_id and meta_app_secret are provided, validates them "
            "via Graph API (app access token) and saves both to KV Store. "
            "Parameters: api_token — Extella API token; base_url — Extella API base URL; "
            "meta_app_id — optional Meta App ID; meta_app_secret — optional App Secret; "
            "open_browser — if true, open Meta for Developers in the system browser (default true)."
        ),
        "kwargs": {
            "api_token": "",
            "base_url": "https://api.extella.ai",
            "meta_app_id": "",
            "meta_app_secret": "",
            "open_browser": True,
        },
        "cspl": "fython",
        "file": "meta_app_onboarding_assistant.py",
    },
    "meta_token_from_browser": {
        "name": "meta_token_from_browser",
        "description": (
            "Extracts Meta (Facebook) Marketing API access token automatically from the user's local browser. "
            "Detects default browser, checks Facebook cookies to verify login status, then opens an OAuth "
            "authorization dialog in the browser and captures the access token via local callback server. "
            "Saves token to KV Store. Returns token and list of ad accounts. "
            "MUST run locally (requires target=device_uuid). "
            "Parameters: api_token — Extella API token; base_url — Extella base URL; "
            "callback_port — local OAuth callback port (default 8891); "
            "oauth_timeout — seconds to wait for user authorization (default 120)."
        ),
        "kwargs": {
            "api_token": "",
            "base_url": "https://api.extella.ai",
            "callback_port": 8891,
            "oauth_timeout": 120,
        },
        "cspl": "fython",
        "file": "meta_token_from_browser.py",
    },
    "meta_site_detector": {
        "name": "meta_site_detector",
        "description": (
            "Detects the CMS/platform of a website by analyzing HTTP headers and HTML content. "
            "Identifies WordPress, Shopify, Wix, Tilda, Bitrix, GTM presence, and custom HTML sites. "
            "Also detects if a Meta Pixel is already installed. "
            "Parameters: url — the landing page URL to analyze; "
            "timeout — HTTP request timeout in seconds (default 15)."
        ),
        "kwargs": {
            "url": "",
            "timeout": 15,
        },
        "cspl": "fython",
        "file": "meta_site_detector.py",
    },
    "meta_pixel_create": {
        "name": "meta_pixel_create",
        "description": (
            "Creates a new Meta (Facebook) Pixel in the specified ad account via Meta Graph API v25. "
            "Returns the pixel_id, pixel_code (full JavaScript snippet with PageView + Lead auto-tracking), "
            "and Events Manager URL. "
            "Parameters: meta_access_token — valid Meta access token with ads_management scope; "
            "ad_account_id — ad account ID (with or without act_ prefix); "
            "pixel_name — optional custom name for the pixel; "
            "landing_url — used to auto-generate pixel name from domain."
        ),
        "kwargs": {
            "meta_access_token": "",
            "ad_account_id": "",
            "pixel_name": "",
            "landing_url": "",
        },
        "cspl": "fython",
        "file": "meta_pixel_create.py",
    },
    "meta_pixel_install_gtm": {
        "name": "meta_pixel_install_gtm",
        "description": (
            "Installs Meta Pixel tag in Google Tag Manager via GTM API v2. "
            "Creates a Custom HTML tag with pixel code, an All Pages trigger, creates a container version, "
            "and publishes it. Falls back to manual instructions if no service account provided. "
            "Parameters: gtm_container_id — GTM container ID (e.g. GTM-XXXXX); "
            "gtm_service_account_json — Google Cloud service account JSON string with Tag Manager permissions; "
            "pixel_code — full pixel HTML code; "
            "pixel_id — pixel ID for labeling; "
            "gtm_workspace_id — workspace ID (default '1')."
        ),
        "kwargs": {
            "gtm_container_id": "",
            "gtm_service_account_json": "",
            "pixel_code": "",
            "pixel_id": "",
            "gtm_workspace_id": "1",
        },
        "cspl": "fython",
        "file": "meta_pixel_install_gtm.py",
    },
    "meta_pixel_install_wp": {
        "name": "meta_pixel_install_wp",
        "description": (
            "Installs Meta Pixel on a WordPress site. Uses WP REST API to detect the active theme, "
            "then injects pixel code into theme header.php via FTP. "
            "Falls back to manual instructions if no FTP credentials provided. "
            "Parameters: wp_url — WordPress site URL; "
            "wp_username — WP admin username; "
            "wp_app_password — WordPress Application Password; "
            "ftp_host — FTP server hostname; "
            "ftp_user — FTP username; "
            "ftp_pass — FTP password; "
            "pixel_code — full pixel HTML code; "
            "pixel_id — pixel ID."
        ),
        "kwargs": {
            "wp_url": "",
            "wp_username": "",
            "wp_app_password": "",
            "ftp_host": "",
            "ftp_user": "",
            "ftp_pass": "",
            "pixel_code": "",
            "pixel_id": "",
        },
        "cspl": "fython",
        "file": "meta_pixel_install_wp.py",
    },
    "meta_pixel_install_shopify": {
        "name": "meta_pixel_install_shopify",
        "description": (
            "Installs Meta Pixel on a Shopify store by injecting code into theme.liquid via Shopify Admin REST API. "
            "Gets the active theme, reads theme.liquid, injects pixel after <head>, and saves. "
            "Falls back to manual instructions if no credentials provided. "
            "Parameters: shop_domain — Shopify store domain (e.g. mystore.myshopify.com); "
            "shopify_access_token — Shopify Admin API access token with write_themes scope; "
            "pixel_code — full pixel HTML code; "
            "pixel_id — pixel ID."
        ),
        "kwargs": {
            "shop_domain": "",
            "shopify_access_token": "",
            "pixel_code": "",
            "pixel_id": "",
        },
        "cspl": "fython",
        "file": "meta_pixel_install_shopify.py",
    },
    "meta_pixel_install_ftp": {
        "name": "meta_pixel_install_ftp",
        "description": (
            "Installs Meta Pixel on a custom HTML site by injecting code via FTP. "
            "Connects to FTP server, auto-detects main HTML file (index.html/index.php) if path not provided, "
            "injects pixel code after <head> tag, and re-uploads the file. "
            "Parameters: ftp_host — FTP server hostname; "
            "ftp_user — FTP username; "
            "ftp_pass — FTP password; "
            "ftp_path — optional specific file path (auto-detected if empty); "
            "pixel_code — full pixel HTML code; "
            "pixel_id — pixel ID; "
            "ftp_port — FTP port (default 21)."
        ),
        "kwargs": {
            "ftp_host": "",
            "ftp_user": "",
            "ftp_pass": "",
            "ftp_path": "",
            "pixel_code": "",
            "pixel_id": "",
            "ftp_port": 21,
        },
        "cspl": "fython",
        "file": "meta_pixel_install_ftp.py",
    },
    "meta_pixel_generate_code": {
        "name": "meta_pixel_generate_code",
        "description": (
            "Generates the complete Meta Pixel HTML code snippet for manual installation. "
            "Includes PageView auto-tracking and Lead event auto-tracking on form submit. "
            "Parameters: pixel_id — the Meta Pixel ID to embed in the code."
        ),
        "kwargs": {
            "pixel_id": "",
        },
        "cspl": "prompt",
        "file": "meta_pixel_generate_code_template.html",
    },
    "meta_pixel_verify": {
        "name": "meta_pixel_verify",
        "description": (
            "Verifies Meta Pixel is active and receiving events. "
            "Sends a test PageView event via Conversions API (CAPI) with test_event_code, "
            "then polls the pixel's last_fired_time field until it confirms the event was received. "
            "Returns pixel_status (active/pending/unavailable), last_fired_time, and Events Manager URL. "
            "Parameters: pixel_id — pixel ID to verify; "
            "meta_access_token — Meta access token; "
            "landing_url — URL used as event_source_url in test event; "
            "wait_seconds — max seconds to wait for verification (default 60)."
        ),
        "kwargs": {
            "pixel_id": "",
            "meta_access_token": "",
            "landing_url": "",
            "wait_seconds": 60,
        },
        "cspl": "fython",
        "file": "meta_pixel_verify.py",
    },
    "meta_pixel_pipeline": {
        "name": "meta_pixel_pipeline",
        "description": (
            "Master orchestrator for Meta Pixel installation. Runs the full pipeline: "
            "1) Creates pixel via meta_pixel_create, "
            "2) Installs via the appropriate platform expert (GTM/WordPress/Shopify/FTP/manual), "
            "3) Verifies via meta_pixel_verify, "
            "4) Returns comprehensive report with pixel_id, install_method, status, events, and links. "
            "Parameters: meta_access_token — Meta access token; "
            "ad_account_id — Meta ad account ID; "
            "landing_url — URL of the landing page; "
            "cms_type — platform type from meta_site_detector (wordpress/shopify/gtm/ftp/wix/tilda/unknown); "
            "cms_credentials — JSON string with platform-specific credentials (see below); "
            "pixel_name — optional custom pixel name; "
            "api_token — Extella API token for calling sub-experts; "
            "base_url — Extella API base URL. "
            "cms_credentials JSON keys by platform: "
            "GTM: {gtm_container_id, gtm_service_account_json}; "
            "WordPress: {wp_username, wp_app_password, ftp_host, ftp_user, ftp_pass}; "
            "Shopify: {shop_domain, shopify_access_token}; "
            "FTP: {ftp_host, ftp_user, ftp_pass, ftp_path}."
        ),
        "kwargs": {
            "meta_access_token": "",
            "ad_account_id": "",
            "landing_url": "",
            "cms_type": "",
            "cms_credentials": "{}",
            "pixel_name": "",
            "api_token": "",
            "base_url": "https://api.extella.ai",
        },
        "cspl": "fython",
        "file": "meta_pixel_pipeline.py",
    },
}

# ─── Publish Concepts ────────────────────────────────────────────────────────

def publish_concepts():
    concept_files = sorted(CONCEPTS_DIR.glob("*.txt"))
    n = len(concept_files)
    reg = load_concept_registry()

    print(f"\n{color('═' * 50, '36')}")
    print(f"{color(f'PUBLISHING CONCEPTS ({n})', '1;36')}")
    print(f"{color('═' * 50, '36')}\n")

    results = []

    for cf in concept_files:
        name = cf.stem
        rel_key = str(cf.relative_to(PRESET_DIR))
        text = read_file(cf)
        print(f"{INF} Concept: {name}")

        existing_id = reg.get(rel_key)
        if existing_id is not None:
            try:
                existing_id = int(existing_id)
            except (TypeError, ValueError):
                existing_id = None

        if existing_id:
            resp = api_post("/api/concept/update", {"concept_id": existing_id, "new_text": text})
            if resp.get("status") == "success":
                print(f"  {OK} Updated  →  concept_id: {existing_id}")
                results.append({"name": name, "id": existing_id, "status": "ok", "action": "update"})
            else:
                print(f"  {ERR} Update failed: {resp}")
                results.append({"name": name, "status": "error", "response": str(resp), "action": "update"})
        else:
            resp = api_post("/api/concept/add", {"text": text})
            if resp.get("status") == "success":
                concept_id = resp.get("id")
                print(f"  {OK} Added  →  concept_id: {concept_id}")
                results.append({"name": name, "id": concept_id, "status": "ok", "action": "add"})
                if concept_id is not None and not DRY_RUN:
                    reg[rel_key] = int(concept_id)
                    save_concept_registry(reg)
            else:
                print(f"  {ERR} Add failed: {resp}")
                results.append({"name": name, "status": "error", "response": str(resp), "action": "add"})

        if not DRY_RUN:
            time.sleep(0.3)

    return results

# ─── Publish Experts ─────────────────────────────────────────────────────────

def publish_experts():
    n_experts = len(EXPERT_META)
    print(f"\n{color('═' * 50, '36')}")
    print(f"{color(f'PUBLISHING EXPERTS ({n_experts})', '1;36')}")
    print(f"{color('═' * 50, '36')}\n")

    results = []

    for expert_key, meta in EXPERT_META.items():
        code_path = EXPERTS_DIR / meta["file"]
        if not code_path.exists():
            print(f"  {ERR} File not found: {code_path}")
            results.append({"name": meta["name"], "status": "error", "reason": "file_not_found"})
            continue

        code = read_file(code_path)
        print(f"{INF} Expert: {meta['name']} (cspl={meta['cspl']})")

        payload = {
            "name": meta["name"],
            "description": meta["description"],
            "code": code,
            "kwargs": meta["kwargs"],
            "cspl": meta["cspl"],
        }

        resp = api_post("/api/expert/save", payload)

        if resp.get("status") == "success":
            print(f"  {OK} Saved  →  {resp.get('expert_name', meta['name'])}")
            results.append({"name": meta["name"], "status": "ok"})
        else:
            print(f"  {ERR} Failed: {resp}")
            results.append({"name": meta["name"], "status": "error", "response": str(resp)})

        if not DRY_RUN:
            time.sleep(0.3)

    return results

# ─── Print Summary ────────────────────────────────────────────────────────────

def print_summary(concept_results, expert_results):
    print(f"\n{color('═' * 50, '36')}")
    print(f"{color('SUMMARY', '1;36')}")
    print(f"{color('═' * 50, '36')}\n")

    c_ok  = sum(1 for r in concept_results if r["status"] == "ok")
    c_err = sum(1 for r in concept_results if r["status"] == "error")
    e_ok  = sum(1 for r in expert_results  if r["status"] == "ok")
    e_err = sum(1 for r in expert_results  if r["status"] == "error")

    print(f"  Concepts:  {color(str(c_ok) + ' published', '32')}  /  {color(str(c_err) + ' failed', '31') if c_err else '0 failed'}")
    print(f"  Experts:   {color(str(e_ok) + ' saved',    '32')}  /  {color(str(e_err) + ' failed', '31') if e_err else '0 failed'}")

    if c_err == 0 and e_err == 0:
        print(f"\n{color('✅ Preset published successfully!', '1;32')}")
    else:
        print(f"\n{color('⚠️  Some items failed. Check errors above.', '1;33')}")

    print(f"\n{color('Next steps:', '1;36')}")
    print("  1. Run meta_app_onboarding_assistant locally to save meta_app_id + meta_app_secret to KV (or set manually)")
    print("  2. Set KV key: extella_device_uuid (from Extella Desktop settings)")
    print("  3. Run meta_token_from_browser locally for OAuth, then use the pixel installer pipeline from chat")
    print()

# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{color('META PIXEL INSTALLER — Preset Bootstrap', '1;35')}")
    print(f"  API: {BASE_URL}")
    if API_TOKEN and len(API_TOKEN) >= 12:
        print(f"  Token: {API_TOKEN[:8]}...{API_TOKEN[-4:]}")
    else:
        print(f"  Token: {color('(set EXTELLA_TOKEN)', '33')}")

    if not DRY_RUN and not (API_TOKEN or "").strip():
        print(f"\n{ERR} EXTELLA_TOKEN is not set. Export it before running bootstrap.")
        sys.exit(1)

    if DRY_RUN:
        print(f"  {color('DRY RUN MODE — no API calls will be made', '1;33')}")

    if SYNC_ONLY:
        if DRY_RUN:
            print(f"{ERR} --sync-concept-registry cannot be combined with --dry-run")
            sys.exit(1)
        try:
            val = requests.post(f"{BASE_URL}/api/token/validate",
                headers=HEADERS,
                json={"token": API_TOKEN}, timeout=10)
            vdata = val.json()
            if not vdata.get("valid"):
                print(f"{ERR} Token invalid: {vdata}")
                sys.exit(1)
            print(f"  {OK} Token valid — user_id: {vdata.get('user_id', '?')}")
        except Exception as e:
            print(f"{ERR} Token validation failed: {e}")
            sys.exit(1)
        ok = sync_concept_registry_from_remote()
        sys.exit(0 if ok else 1)

    # Validate token
    if not DRY_RUN:
        try:
            val = requests.post(f"{BASE_URL}/api/token/validate",
                headers=HEADERS,
                json={"token": API_TOKEN}, timeout=10)
            vdata = val.json()
            if not vdata.get("valid"):
                print(f"{ERR} Token invalid: {vdata}")
                sys.exit(1)
            print(f"  {OK} Token valid — user_id: {vdata.get('user_id', '?')}")
        except Exception as e:
            print(f"{ERR} Token validation failed: {e}")
            sys.exit(1)

    concept_results = publish_concepts()
    expert_results  = publish_experts()
    print_summary(concept_results, expert_results)
