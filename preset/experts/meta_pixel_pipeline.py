$extens("include.py")
include("import requests", ["extella-pip install requests"])

def meta_pixel_pipeline(
    landing_url: str = "",
    cms_type: str = "",
    cms_credentials: str = "{}",
    pixel_name: str = "",
    api_token: str = "",
    base_url: str = "https://api.extella.ai",
    device_uuid: str = "",
    # OAuth path (optional — used only if headless fails)
    meta_access_token: str = "",
    ad_account_id: str = "",
) -> dict:
    import requests
    import json

    if not landing_url:
        return {"status": "error", "message": "landing_url is required"}

    # Parse CMS credentials
    try:
        creds = json.loads(cms_credentials) if cms_credentials else {}
    except Exception:
        creds = {}

    # Helper to call sub-expert (optionally on a local device)
    def run_sub(expert_name, params, timeout=180, target=None):
        payload = {"expert_name": expert_name, "params": params, "timeout": timeout}
        if target:
            payload["target"] = target
        try:
            resp = requests.post(
                f"{base_url}/api/expert/run",
                headers={
                    "X-Auth-Token": api_token,
                    "Content-Type": "application/json",
                    "X-Profile-Id": "default",
                    "X-Agent-Id": "agent_extella_default",
                },
                json=payload,
                timeout=timeout + 15,
            )
            if resp.status_code != 200:
                return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:300]}"}
            data = resp.json()
            return data.get("result", data)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ─── Step 1: Create Pixel ─────────────────────────────────────────────────

    print("[1/4] Creating Meta Pixel...")

    pixel_id = None
    pixel_code = None
    pixel_result = {}
    creation_method = "unknown"

    # ── Path A: Headless browser (no app or token needed) ────────────────────
    if device_uuid:
        print("  [A] Trying headless browser creation...")
        headless_result = run_sub(
            "meta_pixel_create_headless",
            {
                "pixel_name": pixel_name,
                "landing_url": landing_url,
                "api_token": api_token,
                "base_url": base_url,
            },
            timeout=120,
            target=device_uuid,
        )

        if headless_result.get("status") == "setup_required":
            # Playwright not installed — install it, then retry once
            print("  Playwright not ready. Running setup...")
            setup_result = run_sub(
                "meta_playwright_setup",
                {"api_token": api_token, "base_url": base_url},
                timeout=300,
                target=device_uuid,
            )
            if setup_result.get("status") == "ready":
                headless_result = run_sub(
                    "meta_pixel_create_headless",
                    {
                        "pixel_name": pixel_name,
                        "landing_url": landing_url,
                        "api_token": api_token,
                        "base_url": base_url,
                    },
                    timeout=120,
                    target=device_uuid,
                )

        if headless_result.get("status") == "success":
            pixel_id = headless_result["pixel_id"]
            pixel_code = headless_result["pixel_code"]
            pixel_result = headless_result
            creation_method = "headless_browser"
            print(f"  [A] Headless creation OK — pixel_id: {pixel_id}")
        else:
            status = headless_result.get("status", "error")
            print(f"  [A] Headless failed (status={status}): {headless_result.get('message', '')[:120]}")

    # ── Path B: OAuth / Graph API (fallback) ──────────────────────────────────
    if not pixel_id and meta_access_token and ad_account_id:
        print("  [B] Trying OAuth / Graph API creation...")
        api_result = run_sub(
            "meta_pixel_create",
            {
                "meta_access_token": meta_access_token,
                "ad_account_id": ad_account_id,
                "pixel_name": pixel_name,
                "landing_url": landing_url,
            },
            timeout=60,
        )
        if api_result.get("status") == "success":
            pixel_id = api_result["pixel_id"]
            pixel_code = api_result["pixel_code"]
            pixel_result = api_result
            creation_method = "graph_api"
            print(f"  [B] API creation OK — pixel_id: {pixel_id}")
        else:
            print(f"  [B] API creation failed: {api_result.get('message', '')[:120]}")

    if not pixel_id:
        details_parts = []
        if device_uuid:
            details_parts.append(
                f"Headless browser: {headless_result.get('status', '?')} — "
                f"{headless_result.get('message', '')[:150]}"
            )
            if headless_result.get("fallback"):
                details_parts.append(f"Headless fallback hint: {headless_result['fallback']}")
        if meta_access_token and ad_account_id:
            details_parts.append(
                f"Graph API: {api_result.get('status', '?')} — "
                f"{api_result.get('message', '')[:150]}"
            )

        return {
            "status": "error",
            "step": "pixel_creation",
            "message": "Pixel creation failed via all available methods.",
            "details": " | ".join(details_parts) if details_parts else "No creation methods were attempted.",
            "hint": (
                "If headless failed: ensure you are logged into Facebook in your browser and retry. "
                "If Graph API failed: re-run meta_token_from_browser. "
                "If device_uuid is missing: pass it so the agent can run headless locally."
            ),
        }

    print(f"[1/4] Pixel created: {pixel_id} (via {creation_method})")

    # ─── Step 2: Install ───────────────────────────────────────────────────────

    print(f"[2/4] Installing pixel via {cms_type or 'auto-detected method'}...")

    install_result = {}
    install_method = "manual"

    INSTALL_MAP = {
        "gtm": ("meta_pixel_install_gtm", {
            "gtm_container_id": creds.get("gtm_container_id", ""),
            "gtm_service_account_json": creds.get("gtm_service_account_json", ""),
            "pixel_code": pixel_code,
            "pixel_id": pixel_id,
        }),
        "wordpress": ("meta_pixel_install_wp", {
            "wp_url": landing_url,
            "wp_username": creds.get("wp_username", ""),
            "wp_app_password": creds.get("wp_app_password", ""),
            "ftp_host": creds.get("ftp_host", ""),
            "ftp_user": creds.get("ftp_user", ""),
            "ftp_pass": creds.get("ftp_pass", ""),
            "pixel_code": pixel_code,
            "pixel_id": pixel_id,
        }),
        "shopify": ("meta_pixel_install_shopify", {
            "shop_domain": creds.get("shop_domain", ""),
            "shopify_access_token": creds.get("shopify_access_token", ""),
            "pixel_code": pixel_code,
            "pixel_id": pixel_id,
        }),
        "ftp": ("meta_pixel_install_ftp", {
            "ftp_host": creds.get("ftp_host", ""),
            "ftp_user": creds.get("ftp_user", ""),
            "ftp_pass": creds.get("ftp_pass", ""),
            "ftp_path": creds.get("ftp_path", ""),
            "pixel_code": pixel_code,
            "pixel_id": pixel_id,
        }),
        "custom": ("meta_pixel_install_ftp", {
            "ftp_host": creds.get("ftp_host", ""),
            "ftp_user": creds.get("ftp_user", ""),
            "ftp_pass": creds.get("ftp_pass", ""),
            "ftp_path": creds.get("ftp_path", ""),
            "pixel_code": pixel_code,
            "pixel_id": pixel_id,
        }),
        "bitrix": ("meta_pixel_install_ftp", {
            "ftp_host": creds.get("ftp_host", ""),
            "ftp_user": creds.get("ftp_user", ""),
            "ftp_pass": creds.get("ftp_pass", ""),
            "pixel_code": pixel_code,
            "pixel_id": pixel_id,
        }),
    }

    cms_normalized = cms_type.lower().strip() if cms_type else ""

    if cms_normalized in INSTALL_MAP:
        expert_name, expert_params = INSTALL_MAP[cms_normalized]
        install_result = run_sub(expert_name, expert_params, timeout=120)
        install_method = install_result.get("install_method", cms_normalized)
    else:
        install_result = {
            "status": "manual_required",
            "install_method": "manual",
            "pixel_code": pixel_code,
        }
        install_method = "manual"

    is_auto_installed = install_result.get("status") == "success"
    is_already_installed = install_result.get("status") == "already_installed"

    print(f"[2/4] Install result: {install_result.get('status')} via {install_method}")

    # ─── Step 3: Verify ───────────────────────────────────────────────────────

    print("[3/4] Verifying pixel activation...")

    verify_result = {}
    pixel_status = "verification_skipped"

    if meta_access_token:
        verify_result = run_sub(
            "meta_pixel_verify",
            {
                "pixel_id": pixel_id,
                "meta_access_token": meta_access_token,
                "landing_url": landing_url,
                "wait_seconds": 60,
            },
            timeout=120,
        )
        pixel_status = verify_result.get("pixel_status", "pending")
        print(f"[3/4] Pixel status: {pixel_status}")
    else:
        print("[3/4] Skipping verification (no access token — headless mode)")

    # ─── Step 4: Report ───────────────────────────────────────────────────────

    print("[4/4] Building final report...")

    events_active = ["PageView (auto)"]
    if is_auto_installed or is_already_installed:
        events_active.append("Lead (on form submit)")

    report = {
        "status": "success",
        "pixel_id": pixel_id,
        "pixel_name": pixel_result.get("pixel_name", pixel_name),
        "creation_method": creation_method,
        "landing_url": landing_url,
        "cms_type": cms_type,
        "install_method": install_method,
        "install_status": install_result.get("status", "unknown"),
        "pixel_status": pixel_status,
        "events_active": events_active,
        "last_fired_time": verify_result.get("last_fired_time", ""),
        "events_manager_url": (
            f"https://business.facebook.com/events_manager2/list/pixel/{pixel_id}"
        ),
        "test_events_url": (
            f"https://business.facebook.com/events_manager2/list/pixel/{pixel_id}/test_events"
        ),
        "pixel_code": pixel_code,
        "install_details": install_result,
        "verify_details": verify_result,
    }

    if install_result.get("status") == "manual_required":
        report["manual_instructions"] = install_result.get("instructions", "")
        report["message"] = (
            f"Pixel {pixel_id} created via {creation_method}. "
            f"Automatic installation not available for '{cms_type}'. "
            "Please install manually using the pixel code provided."
        )
    elif is_already_installed:
        report["message"] = f"Pixel {pixel_id} was already installed on the site."
    elif is_auto_installed:
        report["message"] = (
            f"Pixel {pixel_id} successfully installed via {install_method}. "
            f"Status: {pixel_status}."
        )
    else:
        report["message"] = (
            f"Pixel {pixel_id} created via {creation_method}. "
            f"Installation encountered an issue: "
            f"{install_result.get('message', 'unknown error')}. "
            "You can install the pixel code manually."
        )

    return report
