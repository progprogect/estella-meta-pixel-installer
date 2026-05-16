$extens("include.py")
include("import requests", ["extella-pip install requests"])
include("from google.oauth2 import service_account", ["extella-pip install google-auth"])

def meta_pixel_install_gtm(
    gtm_container_id: str = "",
    gtm_service_account_json: str = "",
    pixel_code: str = "",
    pixel_id: str = "",
    gtm_workspace_id: str = "1",
) -> dict:
    import requests
    import json

    print("[1/5] Validating GTM credentials...")

    if not pixel_code:
        return {"status": "error", "message": "pixel_code is required"}

    # Manual mode if no service account provided
    if not gtm_service_account_json or not gtm_container_id:
        return {
            "status": "manual_required",
            "install_method": "gtm_manual",
            "message": "GTM service account JSON not provided. Please install manually.",
            "instructions": (
                f"1. Open Google Tag Manager (tagmanager.google.com)\n"
                f"2. Select your container{' ' + gtm_container_id if gtm_container_id else ''}\n"
                f"3. Click Tags → New → Custom HTML\n"
                f"4. Paste the pixel code below\n"
                f"5. Add trigger: All Pages (Page View)\n"
                f"6. Name the tag: 'Meta Pixel — Extella'\n"
                f"7. Save → Submit → Publish"
            ),
            "pixel_code": pixel_code,
        }

    print("[2/5] Authenticating with Google Tag Manager API...")

    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request as GoogleRequest

        SCOPES = [
            "https://www.googleapis.com/auth/tagmanager.edit.containers",
            "https://www.googleapis.com/auth/tagmanager.publish",
        ]
        sa_info = json.loads(gtm_service_account_json)
        creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
        creds.refresh(GoogleRequest())
        access_token = creds.token
        auth_headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    except Exception as e:
        return {"status": "error", "message": f"Google auth failed: {e}"}

    GTM_BASE = "https://tagmanager.googleapis.com/tagmanager/v2"

    print("[3/5] Finding GTM container and account IDs...")

    # Find account and container IDs from GTM container ID (GTM-XXXXX)
    try:
        accounts_resp = requests.get(f"{GTM_BASE}/accounts", headers=auth_headers, timeout=30)
        accounts = accounts_resp.json().get("account", [])

        account_id = container_id = None
        for account in accounts:
            acct_id = account["accountId"]
            containers_resp = requests.get(
                f"{GTM_BASE}/accounts/{acct_id}/containers",
                headers=auth_headers, timeout=30)
            containers = containers_resp.json().get("container", [])
            for c in containers:
                if c.get("publicId", "").upper() == gtm_container_id.upper():
                    account_id = acct_id
                    container_id = c["containerId"]
                    break
            if container_id:
                break

        if not account_id or not container_id:
            return {"status": "error",
                    "message": f"GTM container {gtm_container_id} not found for this service account"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to find GTM container: {e}"}

    workspace_path = f"accounts/{account_id}/containers/{container_id}/workspaces/{gtm_workspace_id}"

    print("[4/5] Creating trigger and tag in GTM...")

    # Create All Pages trigger
    try:
        trigger_resp = requests.post(
            f"{GTM_BASE}/{workspace_path}/triggers",
            headers=auth_headers,
            json={"name": "All Pages — Extella", "type": "PAGEVIEW"},
            timeout=30)
        trigger_data = trigger_resp.json()
        if "triggerId" not in trigger_data:
            gtm_err = trigger_data.get("error", {})
            return {"status": "error", "message": f"Failed to create GTM trigger: {gtm_err.get('message', trigger_data)}"}
        trigger_id = trigger_data["triggerId"]
    except Exception as e:
        return {"status": "error", "message": f"Failed to create GTM trigger: {e}"}

    # Create Custom HTML tag with pixel code
    try:
        tag_resp = requests.post(
            f"{GTM_BASE}/{workspace_path}/tags",
            headers=auth_headers,
            json={
                "name": "Meta Pixel — Extella",
                "type": "html",
                "parameter": [
                    {"type": "template", "key": "html", "value": pixel_code},
                    {"type": "boolean", "key": "supportDocumentWrite", "value": "false"},
                ],
                "firingTriggerId": [trigger_id],
                "notes": f"Meta Pixel {pixel_id} — installed by Extella",
            },
            timeout=30)
        tag_id = tag_resp.json().get("tagId")
    except Exception as e:
        return {"status": "error", "message": f"Failed to create GTM tag: {e}"}

    print("[5/5] Publishing GTM container version...")

    # Create and publish version
    try:
        version_resp = requests.post(
            f"{GTM_BASE}/{workspace_path}:create_version",
            headers=auth_headers,
            json={"name": "Meta Pixel installed by Extella",
                  "notes": f"Auto-installed pixel {pixel_id}"},
            timeout=30)
        version_data = version_resp.json()
        if "containerVersion" not in version_data:
            gtm_err = version_data.get("error", {})
            return {"status": "error", "message": f"Failed to create GTM version: {gtm_err.get('message', version_data)}"}
        version_id = version_data["containerVersion"]["containerVersionId"]

        requests.post(
            f"{GTM_BASE}/accounts/{account_id}/containers/{container_id}/versions/{version_id}:publish",
            headers=auth_headers, timeout=30)
    except Exception as e:
        return {"status": "error", "message": f"Failed to publish GTM version: {e}"}

    return {
        "status": "success",
        "install_method": "gtm_api",
        "gtm_container_id": gtm_container_id,
        "tag_id": tag_id,
        "trigger_id": trigger_id,
        "version_id": version_id,
        "message": f"Meta Pixel tag created and published in GTM container {gtm_container_id}",
    }
