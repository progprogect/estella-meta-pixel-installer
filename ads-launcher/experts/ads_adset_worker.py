$extens("include.py")
include("import requests", ["extella-pip install requests"])

def ads_adset_worker(
    campaign_id: str = "",
    adset_name: str = "",
    targeting_json: str = "{}",
    daily_budget_cents: int = 2000,
    optimization_goal: str = "OFFSITE_CONVERSIONS",
    billing_event: str = "IMPRESSIONS",
    promoted_object_json: str = "{}",
    creative_ids_json: str = "[]",
    meta_token: str = "",
    ad_account_id: str = "",
    # parallel_task metadata
    __description__: str = "",
    api_token: str = "",
    base_url: str = "https://api.extella.ai",
) -> dict:
    import requests
    import json
    import time

    if not campaign_id:
        return {"status": "error", "message": "campaign_id is required"}
    if not meta_token:
        return {"status": "error", "message": "meta_token is required"}
    if not ad_account_id:
        return {"status": "error", "message": "ad_account_id is required"}

    acc = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
    META_VER = "v25.0"

    try:
        targeting = json.loads(targeting_json) if targeting_json else {}
    except Exception:
        targeting = {}

    try:
        promoted_object = json.loads(promoted_object_json) if promoted_object_json else {}
    except Exception:
        promoted_object = {}

    try:
        creative_ids = json.loads(creative_ids_json) if creative_ids_json else []
    except Exception:
        creative_ids = []

    # ── Create Ad Set ─────────────────────────────────────────────────────────
    print(f"[1/2] Creating ad set: {adset_name}...")
    start_time = int(time.time()) + 600  # 10 minutes from now

    adset_payload = {
        "name": adset_name,
        "campaign_id": campaign_id,
        "billing_event": billing_event,
        "optimization_goal": optimization_goal,
        "daily_budget": daily_budget_cents,
        "targeting": targeting,
        "status": "PAUSED",
        "start_time": start_time,
        "access_token": meta_token,
    }
    if promoted_object:
        adset_payload["promoted_object"] = promoted_object

    adset_resp = requests.post(
        f"https://graph.facebook.com/{META_VER}/{acc}/adsets",
        json=adset_payload,
        timeout=30,
    )
    if adset_resp.status_code != 200:
        err = adset_resp.json().get("error", {}).get("message", adset_resp.text[:300])
        return {"status": "error", "step": "adset_create", "adset_name": adset_name, "message": err}

    adset_id = adset_resp.json().get("id")
    print(f"  Ad Set created: {adset_id}")

    # ── Create Ads ────────────────────────────────────────────────────────────
    print(f"[2/2] Creating ads for ad set {adset_id}...")
    ad_ids = []
    ad_errors = []

    for i, creative_id in enumerate(creative_ids):
        ad_name = f"{adset_name} — Ad {i+1}"
        ad_resp = requests.post(
            f"https://graph.facebook.com/{META_VER}/{acc}/ads",
            json={
                "name": ad_name,
                "adset_id": adset_id,
                "creative": {"creative_id": creative_id},
                "status": "PAUSED",
                "access_token": meta_token,
            },
            timeout=30,
        )
        if ad_resp.status_code == 200:
            ad_id = ad_resp.json().get("id")
            ad_ids.append(ad_id)
            print(f"  Ad created: {ad_id}")
        else:
            err = ad_resp.json().get("error", {}).get("message", ad_resp.text[:200])
            ad_errors.append(f"Ad {i+1}: {err}")

    return {
        "status": "success",
        "adset_id": adset_id,
        "adset_name": adset_name,
        "ad_ids": ad_ids,
        "ad_errors": ad_errors,
        "message": (
            f"Ad set '{adset_name}' created ({adset_id}) with {len(ad_ids)} ad(s)."
            + (f" Errors: {ad_errors}" if ad_errors else "")
        ),
    }
