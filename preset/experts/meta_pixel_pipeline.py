$extens("include.py")
include("import requests", ["extella-pip install requests"])

def meta_pixel_pipeline(
    meta_access_token: str = "",
    ad_account_id: str = "",
    landing_url: str = "",
    cms_type: str = "",
    cms_credentials: str = "{}",
    pixel_name: str = "",
    api_token: str = "",
    base_url: str = "https://api.extella.ai",
) -> dict:
    import requests
    import json

    if not meta_access_token or not ad_account_id or not landing_url:
        return {"status": "error",
                "message": "meta_access_token, ad_account_id, and landing_url are required"}

    # Parse CMS credentials
    try:
        creds = json.loads(cms_credentials) if cms_credentials else {}
    except Exception:
        creds = {}

    # Helper to call sub-expert
    def run_sub(expert_name, params, timeout=180):
        try:
            resp = requests.post(
                f"{base_url}/api/expert/run",
                headers={
                    "X-Auth-Token": api_token,
                    "Content-Type": "application/json",
                    "X-Profile-Id": "default",
                    "X-Agent-Id": "agent_extella_default",
                },
                json={"expert_name": expert_name, "params": params, "timeout": timeout},
                timeout=timeout + 15,
            )
            if resp.status_code != 200:
                return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:300]}"}
            data = resp.json()
            return data.get("result", data)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    print("[1/4] Creating Meta Pixel...")

    # Step 1: Create Pixel
    pixel_result = run_sub("meta_pixel_create", {
        "meta_access_token": meta_access_token,
        "ad_account_id": ad_account_id,
        "pixel_name": pixel_name,
        "landing_url": landing_url,
    })

    if pixel_result.get("status") != "success":
        return {
            "status": "error",
            "step": "pixel_creation",
            "message": pixel_result.get("message", "Pixel creation failed"),
            "details": pixel_result,
        }

    pixel_id = pixel_result["pixel_id"]
    pixel_code = pixel_result["pixel_code"]
    print(f"[1/4] Pixel created: {pixel_id}")

    print(f"[2/4] Installing pixel via {cms_type or 'auto-detected method'}...")

    # Step 2: Install
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
        # Manual mode for Wix, Tilda, unknown
        install_result = {
            "status": "manual_required",
            "install_method": "manual",
            "pixel_code": pixel_code,
        }
        install_method = "manual"

    is_auto_installed = install_result.get("status") == "success"
    is_already_installed = install_result.get("status") == "already_installed"

    print(f"[2/4] Install result: {install_result.get('status')} via {install_method}")

    print("[3/4] Verifying pixel activation...")

    # Step 3: Verify
    verify_result = run_sub("meta_pixel_verify", {
        "pixel_id": pixel_id,
        "meta_access_token": meta_access_token,
        "landing_url": landing_url,
        "wait_seconds": 60,
    }, timeout=120)

    pixel_status = verify_result.get("pixel_status", "pending")
    print(f"[3/4] Pixel status: {pixel_status}")

    print("[4/4] Building final report...")

    # Step 4: Build comprehensive report
    events_active = ["PageView (auto)"]
    if is_auto_installed or is_already_installed:
        events_active.append("Lead (on form submit)")

    report = {
        "status": "success",
        "pixel_id": pixel_id,
        "pixel_name": pixel_result.get("pixel_name", ""),
        "ad_account_id": ad_account_id,
        "landing_url": landing_url,
        "cms_type": cms_type,
        "install_method": install_method,
        "install_status": install_result.get("status", "unknown"),
        "pixel_status": pixel_status,
        "events_active": events_active,
        "last_fired_time": verify_result.get("last_fired_time", ""),
        "events_manager_url": f"https://business.facebook.com/events_manager2/list/pixel/{pixel_id}",
        "test_events_url": f"https://business.facebook.com/events_manager2/list/pixel/{pixel_id}/test_events",
        "pixel_code": pixel_code,
        "install_details": install_result,
        "verify_details": verify_result,
    }

    # Add manual instructions if needed
    if install_result.get("status") == "manual_required":
        report["manual_instructions"] = install_result.get("instructions", "")
        report["message"] = (
            f"Pixel {pixel_id} created. Automatic installation not available for {cms_type}. "
            "Please install manually using the instructions provided."
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
            f"Pixel {pixel_id} created. Installation encountered an issue: "
            f"{install_result.get('message', 'unknown error')}. "
            "You can install the pixel code manually."
        )

    return report
