$extens("include.py")
include("import requests", ["extella-pip install requests"])

def ads_campaign_create(
    campaign_name: str = "",
    pixel_id: str = "",
    conversion_goal: str = "purchase",
    budget_daily: str = "50",
    targeting_specs_json: str = "[]",
    creative_ids_json: str = "[]",
    ad_account_id: str = "",
    meta_token: str = "",
    device_uuid: str = "",
    api_token: str = "",
    base_url: str = "https://api.extella.ai",
) -> dict:
    import requests
    import json
    import time

    if not meta_token:
        return {"status": "error", "message": "meta_token is required"}
    if not ad_account_id:
        return {"status": "error", "message": "ad_account_id is required"}
    if not pixel_id:
        return {"status": "error", "message": "pixel_id is required"}

    acc = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
    META_VER = "v25.0"

    try:
        budget = float(str(budget_daily).replace("$", "").strip())
    except ValueError:
        return {"status": "error", "message": f"budget_daily must be a number, got: {budget_daily}"}

    budget_cents = int(budget * 100)

    try:
        targeting_specs = json.loads(targeting_specs_json) if targeting_specs_json else []
    except Exception:
        targeting_specs = []

    try:
        creative_ids = json.loads(creative_ids_json) if creative_ids_json else []
    except Exception:
        creative_ids = []

    if not targeting_specs:
        return {"status": "error", "message": "targeting_specs_json is required (run ads_audience_builder first)"}
    if not creative_ids:
        return {"status": "error", "message": "creative_ids_json is required (run ads_creative_upload first)"}

    GOAL_OBJECTIVE_MAP = {
        "purchase": "OUTCOME_SALES",
        "lead": "OUTCOME_LEADS",
        "complete_registration": "OUTCOME_LEADS",
        "app_install": "OUTCOME_APP_PROMOTION",
    }
    GOAL_OPTIMIZATION_MAP = {
        "purchase": "OFFSITE_CONVERSIONS",
        "lead": "LEAD_GENERATION",
        "complete_registration": "OFFSITE_CONVERSIONS",
        "app_install": "APP_INSTALLS",
    }
    GOAL_EVENT_MAP = {
        "purchase": "PURCHASE",
        "lead": "LEAD",
        "complete_registration": "COMPLETE_REGISTRATION",
        "app_install": None,
    }

    goal = conversion_goal.lower()
    objective = GOAL_OBJECTIVE_MAP.get(goal, "OUTCOME_SALES")
    optimization_goal = GOAL_OPTIMIZATION_MAP.get(goal, "OFFSITE_CONVERSIONS")
    custom_event_type = GOAL_EVENT_MAP.get(goal)

    if not campaign_name:
        campaign_name = f"Ads Launcher — {goal.title()} — {time.strftime('%Y-%m-%d')}"

    headers_ext = {
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
                headers=headers_ext,
                json=payload,
                timeout=timeout + 15,
            )
            if resp.status_code != 200:
                return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:300]}"}
            data = resp.json()
            return data.get("result", data)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def kv_set(key: str, value: str) -> bool:
        try:
            r = requests.post(
                f"{base_url}/api/kv/set",
                headers=headers_ext,
                json={"key": key, "value": value},
                timeout=10,
            )
            return r.status_code == 200
        except Exception:
            return False

    # ── Step 1: Create Campaign (PAUSED) ──────────────────────────────────────
    print("[1/4] Creating campaign (PAUSED)...")
    campaign_resp = requests.post(
        f"https://graph.facebook.com/{META_VER}/{acc}/campaigns",
        json={
            "name": campaign_name,
            "objective": objective,
            "status": "PAUSED",
            "special_ad_categories": [],
            "access_token": meta_token,
        },
        timeout=30,
    )
    if campaign_resp.status_code != 200:
        err = campaign_resp.json().get("error", {}).get("message", campaign_resp.text[:300])
        return {"status": "error", "step": "campaign_create", "message": err}

    campaign_id = campaign_resp.json().get("id")
    print(f"  Campaign created: {campaign_id}")

    # ── Step 2: Fan-out ad set creation (parallel_task) ──────────────────────
    print("[2/4] Launching ad set workers in parallel...")

    promoted_object = {"pixel_id": pixel_id}
    if custom_event_type:
        promoted_object["custom_event_type"] = custom_event_type

    budget_split = [0.4, 0.3, 0.3]  # cold, warm, lookalike
    adset_names = ["Cold — Interests", "Warm — Retargeting", "Lookalike 1%"]

    worker_futures = []
    for i, spec in enumerate(targeting_specs[:3]):
        split_budget_cents = int(budget_cents * budget_split[i])
        if split_budget_cents < 100:
            split_budget_cents = 100  # minimum $1/day per ad set

        worker_params = {
            "campaign_id": campaign_id,
            "adset_name": f"{adset_names[i]} — {campaign_name}",
            "targeting_json": spec.get("targeting_json", "{}"),
            "daily_budget_cents": split_budget_cents,
            "optimization_goal": optimization_goal,
            "billing_event": "IMPRESSIONS",
            "promoted_object_json": json.dumps(promoted_object),
            "creative_ids_json": creative_ids_json,
            "meta_token": meta_token,
            "ad_account_id": ad_account_id,
            "__description__": spec.get("name", adset_names[i]),
            "api_token": api_token,
            "base_url": base_url,
        }
        future = run_sub("ads_adset_worker", worker_params, timeout=120)
        worker_futures.append(future)

    # Collect UUIDs for parallel tracking
    task_uuids = [f.get("uuid") for f in worker_futures if f.get("uuid")]
    if task_uuids:
        print(f"  Waiting for {len(task_uuids)} parallel tasks (UUIDs: {task_uuids})...")
        wait_result = run_sub(
            "demo_wait_tasks",
            {"uuids": json.dumps(task_uuids)},
            timeout=300,
        )
        final_results = wait_result.get("results", worker_futures)
    else:
        final_results = worker_futures

    # ── Step 3: Collect ad set results ───────────────────────────────────────
    print("[3/4] Collecting ad set results...")
    adset_ids = []
    all_ad_ids = []
    adset_errors = []
    structure_lines = []

    for result in final_results:
        if isinstance(result, dict) and result.get("status") == "success":
            adset_id = result.get("adset_id")
            ad_ids = result.get("ad_ids", [])
            adset_ids.append(adset_id)
            all_ad_ids.extend(ad_ids)
            structure_lines.append(
                f"  Ad Set: {result.get('adset_name')} ({adset_id}) → {len(ad_ids)} ads"
            )
        else:
            err = result.get("message", str(result))
            adset_errors.append(err)
            structure_lines.append(f"  [ERROR] {err[:100]}")

    if not adset_ids:
        return {
            "status": "error",
            "step": "adset_create",
            "campaign_id": campaign_id,
            "message": "All ad set creation attempts failed",
            "errors": adset_errors,
        }

    # ── Step 4: Save IDs to KV ────────────────────────────────────────────────
    print("[4/4] Saving campaign IDs to KV...")
    kv_set("ads_campaign_id", campaign_id)
    kv_set("ads_adset_ids", json.dumps(adset_ids))
    kv_set("ads_ad_ids", json.dumps(all_ad_ids))

    structure_summary = (
        f"Campaign: {campaign_name} ({campaign_id}) [PAUSED]\n"
        + "\n".join(structure_lines)
    )

    return {
        "status": "success",
        "campaign_id": campaign_id,
        "adset_ids": adset_ids,
        "ad_ids": all_ad_ids,
        "adset_errors": adset_errors,
        "structure_summary": structure_summary,
        "message": (
            f"Campaign created with {len(adset_ids)} ad set(s) and {len(all_ad_ids)} ad(s). "
            f"All PAUSED — awaiting your confirmation to launch."
            + (f" ({len(adset_errors)} ad set error(s))" if adset_errors else "")
        ),
    }
