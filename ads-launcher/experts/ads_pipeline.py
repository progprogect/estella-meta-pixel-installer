$extens("include.py")
include("import requests", ["extella-pip install requests"])

def ads_pipeline(
    # User inputs (can be pre-saved in KV or passed directly)
    product_info: str = "",
    audience_desc: str = "",
    budget_daily: str = "",
    conversion_goal: str = "",
    ad_account_id: str = "",
    meta_token: str = "",
    pixel_id: str = "",
    page_id: str = "",
    creatives_json: str = "",
    ad_copy: str = "",
    headline: str = "",
    link_url: str = "",
    call_to_action: str = "LEARN_MORE",
    target_cpa: str = "",
    git_repo_url: str = "",
    github_token: str = "",
    capi_token: str = "",
    # Control
    step: str = "all",
    device_uuid: str = "",
    api_token: str = "",
    base_url: str = "https://api.extella.ai",
) -> dict:
    """
    Main orchestrator for the Meta Ads Launcher preset.
    step: "all"      — run full pipeline end-to-end
          "intake"   — only validate inputs (Step 0)
          "capi"     — only install CAPI (Step 1)
          "audience" — only build audiences (Step 2)
          "creative" — only upload creatives (Step 3)
          "campaign" — only create campaign (Step 4)
          "launch"   — unpause and start monitor (Step 5)
    """
    import requests
    import json

    headers = {
        "X-Auth-Token": api_token,
        "Content-Type": "application/json",
        "X-Profile-Id": "default",
        "X-Agent-Id": "agent_extella_default",
    }

    def run_sub(expert_name, params, timeout=180, target=None):
        payload = {"expert_name": expert_name, "params": params, "timeout": timeout}
        if target:
            payload["target"] = target
        try:
            resp = requests.post(
                f"{base_url}/api/expert/run",
                headers=headers,
                json=payload,
                timeout=timeout + 15,
            )
            if resp.status_code != 200:
                return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:300]}"}
            data = resp.json()
            return data.get("result", data)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def kv_get(key):
        try:
            r = requests.get(
                f"{base_url}/api/kv/get",
                headers=headers,
                params={"key": key},
                timeout=10,
            )
            if r.status_code == 200:
                return r.json().get("value") or ""
        except Exception:
            pass
        return ""

    def kv_set(key, value):
        try:
            requests.post(
                f"{base_url}/api/kv/set",
                headers=headers,
                json={"key": key, "value": str(value)},
                timeout=10,
            )
        except Exception:
            pass

    def resolve(val, kv_key):
        return val.strip() if val and val.strip() else (kv_get(kv_key) or "")

    # ── Load from KV if not passed ─────────────────────────────────────────────
    product_info = resolve(product_info, "ads_product_info")
    audience_desc = resolve(audience_desc, "ads_audience_desc")
    budget_daily = resolve(budget_daily, "ads_budget_daily")
    conversion_goal = resolve(conversion_goal, "ads_conversion_goal")
    ad_account_id = resolve(ad_account_id, "ads_ad_account_id")
    meta_token = resolve(meta_token, "ads_meta_token")
    pixel_id = resolve(pixel_id, "ads_pixel_id")
    page_id = resolve(page_id, "ads_page_id")
    creatives_json = resolve(creatives_json, "ads_creatives")
    target_cpa = resolve(target_cpa, "ads_target_cpa")
    git_repo_url = resolve(git_repo_url, "ads_git_repo_url")
    capi_token = resolve(capi_token, "ads_capi_token")
    device_uuid = resolve(device_uuid, "extella_device_uuid")

    results = {}
    progress = []

    def log(msg):
        print(msg, flush=True)
        progress.append(msg)

    # ── STEP 0: Intake ────────────────────────────────────────────────────────
    if step in ("all", "intake"):
        log("[STEP 0] Validating inputs...")
        intake_result = run_sub("ads_intake", {
            "product_info": product_info,
            "audience_desc": audience_desc,
            "budget_daily": budget_daily,
            "conversion_goal": conversion_goal,
            "ad_account_id": ad_account_id,
            "meta_token": meta_token,
            "pixel_id": pixel_id,
            "capi_token": capi_token,
            "git_repo_url": git_repo_url,
            "target_cpa": target_cpa,
            "creatives": creatives_json,
            "page_id": page_id,
            "api_token": api_token,
            "base_url": base_url,
        })
        results["intake"] = intake_result

        if intake_result.get("status") == "needs_input":
            return {
                "status": "needs_input",
                "missing": intake_result.get("missing", []),
                "message": intake_result.get("message", "Missing required inputs."),
                "progress": progress,
            }
        if intake_result.get("status") == "error":
            return {"status": "error", "step": "intake", "message": intake_result.get("message"), "progress": progress}

        validated = intake_result.get("validated", {})
        ad_account_id = validated.get("ad_account_id", ad_account_id)
        log(f"  ✅ Inputs validated. Budget: ${validated.get('budget_daily_usd')}/day, "
            f"Goal: {validated.get('conversion_goal')}")

        if step == "intake":
            return {"status": "success", "step_completed": "intake", "result": intake_result, "progress": progress}

    # ── STEP 1: CAPI via Git ──────────────────────────────────────────────────
    if step in ("all", "capi"):
        if git_repo_url and capi_token and pixel_id and device_uuid:
            log("[STEP 1] Installing CAPI into website repository...")
            capi_result = run_sub("ads_capi_git_install", {
                "repo_url": git_repo_url,
                "pixel_id": pixel_id,
                "capi_token": capi_token,
                "github_token": github_token,
                "api_token": api_token,
                "base_url": base_url,
                "device_uuid": device_uuid,
            }, timeout=240, target=device_uuid)
            results["capi"] = capi_result

            if capi_result.get("status") == "success":
                pr_url = capi_result.get("pr_url")
                log(f"  ✅ CAPI integration created. Branch: capi-integration."
                    + (f" PR: {pr_url}" if pr_url else ""))
                if pr_url and pr_url.startswith("http"):
                    return {
                        "status": "waiting_for_merge",
                        "pr_url": pr_url,
                        "message": (
                            f"CAPI integration is ready! Please review and merge the PR:\n{pr_url}\n\n"
                            "After merging, run ads_pipeline with step='audience' to continue."
                        ),
                        "progress": progress,
                        "results": results,
                    }
            else:
                log(f"  ⚠️  CAPI install failed: {capi_result.get('message', 'unknown error')}. Continuing without CAPI.")
        else:
            log("[STEP 1] CAPI skipped (missing git_repo_url, capi_token, pixel_id, or device_uuid).")
            results["capi"] = {"status": "skipped", "reason": "missing git_repo_url or capi_token"}

        if step == "capi":
            return {"status": "success", "step_completed": "capi", "result": results.get("capi"), "progress": progress}

    # ── STEP 2: Build audiences ───────────────────────────────────────────────
    if step in ("all", "audience"):
        log("[STEP 2] Building targeting audiences...")
        audience_result = run_sub("ads_audience_builder", {
            "audience_desc": audience_desc,
            "conversion_goal": conversion_goal,
            "pixel_id": pixel_id,
            "ad_account_id": ad_account_id,
            "meta_token": meta_token,
            "api_token": api_token,
            "base_url": base_url,
        }, timeout=120)
        results["audience"] = audience_result

        if audience_result.get("status") != "success":
            return {"status": "error", "step": "audience", "message": audience_result.get("message"), "progress": progress}

        targeting_specs_json = json.dumps(audience_result.get("targeting_specs", []))
        kv_set("ads_targeting_specs", targeting_specs_json)

        summaries = audience_result.get("audience_summaries", [])
        log(f"  ✅ {len(summaries)} audience segments built:")
        for s in summaries:
            log(f"     - {s}")

        if step == "audience":
            return {"status": "success", "step_completed": "audience", "result": audience_result, "progress": progress}
    else:
        targeting_specs_json = kv_get("ads_targeting_specs") or "[]"

    # ── STEP 3: Upload creatives ──────────────────────────────────────────────
    if step in ("all", "creative"):
        if not creatives_json:
            return {
                "status": "needs_input",
                "missing": ["creatives_json"],
                "message": "Please provide ad creatives (image URLs or base64 strings).",
                "progress": progress,
            }

        log("[STEP 3] Uploading ad creatives...")
        creative_result = run_sub("ads_creative_upload", {
            "creatives_json": creatives_json,
            "ad_copy": ad_copy,
            "headline": headline,
            "link_url": link_url,
            "call_to_action": call_to_action,
            "page_id": page_id,
            "ad_account_id": ad_account_id,
            "meta_token": meta_token,
            "api_token": api_token,
            "base_url": base_url,
        }, timeout=120)
        results["creative"] = creative_result

        if creative_result.get("status") != "success":
            return {"status": "error", "step": "creative", "message": creative_result.get("message"), "progress": progress}

        creative_ids = creative_result.get("creative_ids", [])
        creative_ids_json = json.dumps(creative_ids)
        kv_set("ads_creative_ids", creative_ids_json)
        log(f"  ✅ {len(creative_ids)} creative(s) uploaded: {creative_ids}")

        if step == "creative":
            return {"status": "success", "step_completed": "creative", "result": creative_result, "progress": progress}
    else:
        creative_ids_json = kv_get("ads_creative_ids") or "[]"

    # ── STEP 4: Create campaign ───────────────────────────────────────────────
    if step in ("all", "campaign"):
        log("[STEP 4] Creating campaign structure (PAUSED)...")
        campaign_result = run_sub("ads_campaign_create", {
            "pixel_id": pixel_id,
            "conversion_goal": conversion_goal,
            "budget_daily": budget_daily,
            "targeting_specs_json": targeting_specs_json,
            "creative_ids_json": creative_ids_json,
            "ad_account_id": ad_account_id,
            "meta_token": meta_token,
            "device_uuid": device_uuid,
            "api_token": api_token,
            "base_url": base_url,
        }, timeout=300)
        results["campaign"] = campaign_result

        if campaign_result.get("status") != "success":
            return {"status": "error", "step": "campaign", "message": campaign_result.get("message"), "progress": progress}

        campaign_id = campaign_result.get("campaign_id")
        adset_ids = campaign_result.get("adset_ids", [])
        log(f"  ✅ Campaign created: {campaign_id}")
        log(f"  Ad sets: {adset_ids}")

        return {
            "status": "awaiting_launch_confirmation",
            "campaign_id": campaign_id,
            "adset_ids": adset_ids,
            "structure_summary": campaign_result.get("structure_summary"),
            "message": (
                "Campaign structure is ready and PAUSED.\n\n"
                + campaign_result.get("structure_summary", "") + "\n\n"
                "To launch campaigns, call ads_pipeline with step='launch' "
                "(or tell the agent 'launch the campaigns')."
            ),
            "progress": progress,
            "results": results,
        }

    # ── STEP 5: Launch (unpause) and start monitor ────────────────────────────
    if step == "launch":
        campaign_id = kv_get("ads_campaign_id")
        adset_ids_str = kv_get("ads_adset_ids")
        try:
            adset_ids = json.loads(adset_ids_str) if adset_ids_str else []
        except Exception:
            adset_ids = []

        if not campaign_id:
            return {"status": "error", "step": "launch", "message": "No campaign_id found in KV — run campaign creation step first."}

        log("[STEP 5] Unpausing campaigns...")
        unpause_result = run_sub("ads_optimizer", {
            "action": "unpause",
            "adset_ids_json": json.dumps(adset_ids),
            "campaign_id": campaign_id,
            "meta_token": meta_token,
            "confirm": True,
            "api_token": api_token,
            "base_url": base_url,
        })
        results["unpause"] = unpause_result
        log(f"  ✅ {unpause_result.get('message', 'Campaigns activated.')}")

        log("[STEP 5] Starting monitoring daemon...")
        monitor_result = run_sub("ads_monitor", {
            "api_token": api_token,
            "meta_token": meta_token,
            "campaign_id": campaign_id,
            "adset_ids_json": json.dumps(adset_ids),
            "conversion_goal": conversion_goal,
            "target_cpa": target_cpa or "0",
            "base_url": base_url,
        }, timeout=10, target=device_uuid if device_uuid else None)
        results["monitor"] = monitor_result

        pid = monitor_result.get("pid")
        kv_set("ads_monitor_pid", str(pid or ""))
        log(f"  ✅ Monitor daemon started (PID: {pid}).")

        return {
            "status": "launched",
            "campaign_id": campaign_id,
            "adset_ids": adset_ids,
            "monitor_pid": pid,
            "message": (
                "🚀 Campaigns are LIVE!\n\n"
                f"Campaign ID: {campaign_id}\n"
                f"Ad Sets: {adset_ids}\n"
                f"Monitor PID: {pid}\n\n"
                "I'm now monitoring performance every 6 hours.\n"
                "You'll receive daily reports and I'll alert you at 50 and 100 conversion events."
            ),
            "progress": progress,
            "results": results,
        }

    return {
        "status": "error",
        "message": f"Unknown step: '{step}'. Valid values: all, intake, capi, audience, creative, campaign, launch",
        "progress": progress,
    }
