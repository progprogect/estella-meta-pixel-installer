$extens("include.py")
include("import requests", ["extella-pip install requests"])

def ads_optimizer(
    action: str = "auto",
    adset_ids_json: str = "[]",
    campaign_id: str = "",
    conversion_goal: str = "purchase",
    target_cpa: str = "0",
    meta_token: str = "",
    confirm: bool = False,
    api_token: str = "",
    base_url: str = "https://api.extella.ai",
) -> dict:
    """
    action: "auto"   — analyze and apply recommendations automatically
            "pause"  — pause all underperforming ad sets (CPA > 2x target or $50 spend / 0 conv)
            "scale"  — scale budgets +20% for best performers (CPA < 0.8x target, conv >= 10)
            "unpause" — activate all ad sets (set status ACTIVE)
            "report" — only return recommendations, no changes
    confirm: if False (default), return pending_actions for user approval
             if True, apply changes immediately
    """
    import requests
    import json

    if not meta_token:
        return {"status": "error", "message": "meta_token is required"}

    META_VER = "v25.0"
    try:
        adset_ids = json.loads(adset_ids_json) if adset_ids_json else []
    except Exception:
        adset_ids = []

    try:
        t_cpa = float(str(target_cpa).replace("$", "").strip())
    except (ValueError, TypeError):
        t_cpa = 0.0

    GOAL_ACTION_MAP = {
        "purchase": "offsite_conversion.fb_pixel_purchase",
        "lead": "offsite_conversion.fb_pixel_lead",
        "complete_registration": "offsite_conversion.fb_pixel_complete_registration",
        "app_install": "mobile_app_install",
    }
    action_type = GOAL_ACTION_MAP.get(conversion_goal.lower(), "offsite_conversion.fb_pixel_purchase")

    def get_adset_data(adset_id):
        adset_info = {}
        insights = {}
        try:
            r = requests.get(
                f"https://graph.facebook.com/{META_VER}/{adset_id}",
                params={
                    "fields": "name,daily_budget,learning_stage_info,effective_status",
                    "access_token": meta_token,
                },
                timeout=15,
            )
            if r.status_code == 200:
                adset_info = r.json()
        except Exception:
            pass
        try:
            r = requests.get(
                f"https://graph.facebook.com/{META_VER}/{adset_id}/insights",
                params={
                    "fields": "spend,actions,cost_per_action_type",
                    "date_preset": "last_7d",
                    "access_token": meta_token,
                },
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json().get("data", [])
                insights = data[0] if data else {}
        except Exception:
            pass
        conversions = 0
        spend = 0.0
        for a in insights.get("actions", []):
            if a.get("action_type") == action_type:
                try:
                    conversions += int(float(a.get("value", 0)))
                except (ValueError, TypeError):
                    pass
        spend = float(insights.get("spend", 0))
        cpa = spend / conversions if conversions > 0 else 0.0
        learning = adset_info.get("learning_stage_info", {})
        learning_status = learning.get("status") if learning else None
        daily_budget = int(adset_info.get("daily_budget", 0))
        return {
            "adset_id": adset_id,
            "name": adset_info.get("name", adset_id),
            "effective_status": adset_info.get("effective_status", "UNKNOWN"),
            "learning_status": learning_status,
            "daily_budget_cents": daily_budget,
            "spend": spend,
            "conversions": conversions,
            "cpa": cpa,
        }

    def apply_change(adset_id, payload):
        try:
            r = requests.post(
                f"https://graph.facebook.com/{META_VER}/{adset_id}",
                json={**payload, "access_token": meta_token},
                timeout=20,
            )
            if r.status_code == 200:
                return True, None
            err = r.json().get("error", {}).get("message", r.text[:200])
            return False, err
        except Exception as e:
            return False, str(e)

    # ── Unpause (activate) all ad sets or campaign ────────────────────────────
    if action == "unpause":
        targets = []
        if campaign_id:
            targets.append(("campaign", campaign_id))
        for adset_id in adset_ids:
            targets.append(("adset", adset_id))

        results = []
        for kind, obj_id in targets:
            url = f"https://graph.facebook.com/{META_VER}/{obj_id}"
            try:
                r = requests.post(
                    url,
                    json={"status": "ACTIVE", "access_token": meta_token},
                    timeout=20,
                )
                ok = r.status_code == 200
                results.append({"id": obj_id, "type": kind, "success": ok,
                                 "error": r.json().get("error", {}).get("message") if not ok else None})
            except Exception as e:
                results.append({"id": obj_id, "type": kind, "success": False, "error": str(e)})

        success_count = sum(1 for r in results if r["success"])
        return {
            "status": "success",
            "action": "unpause",
            "results": results,
            "message": f"Activated {success_count}/{len(results)} campaign/ad set(s).",
        }

    # ── Analyze all ad sets ───────────────────────────────────────────────────
    adset_data = [get_adset_data(adset_id) for adset_id in adset_ids]

    pending_pause = []
    pending_scale = []

    for adset in adset_data:
        cpa = adset["cpa"]
        spend = adset["spend"]
        conv = adset["conversions"]
        ls = adset["learning_status"]
        budget = adset["daily_budget_cents"]
        name = adset["name"]
        adset_id = adset["adset_id"]

        if action in ("auto", "pause"):
            should_pause = False
            reason = ""
            if ls == "FAIL":
                should_pause = True
                reason = "learning phase FAIL"
            elif t_cpa > 0 and cpa > t_cpa * 2 and spend > 50:
                should_pause = True
                reason = f"CPA ${cpa:.2f} is {cpa/t_cpa:.1f}x target"
            elif conv == 0 and spend > 50:
                should_pause = True
                reason = f"${spend:.0f} spent with 0 conversions"

            if should_pause:
                pending_pause.append({
                    "adset_id": adset_id,
                    "name": name,
                    "reason": reason,
                    "action": "pause",
                    "payload": {"status": "PAUSED"},
                })

        if action in ("auto", "scale"):
            should_scale = (
                ls == "SUCCESS"
                and t_cpa > 0
                and cpa < t_cpa * 0.8
                and conv >= 10
                and budget > 0
            )
            if should_scale:
                new_budget = int(budget * 1.2)
                pending_scale.append({
                    "adset_id": adset_id,
                    "name": name,
                    "reason": f"CPA ${cpa:.2f} below target — scaling +20%",
                    "action": "scale",
                    "from_budget_cents": budget,
                    "to_budget_cents": new_budget,
                    "payload": {"daily_budget": new_budget},
                })

    all_pending = pending_pause + pending_scale

    if action == "report" or (not confirm and all_pending):
        return {
            "status": "pending_approval" if all_pending else "no_action_needed",
            "pending_actions": all_pending,
            "adset_analysis": adset_data,
            "message": (
                f"{len(pending_pause)} ad set(s) to pause, {len(pending_scale)} to scale. "
                "Call with confirm=True to apply."
                if all_pending else "No optimization actions needed at this time."
            ),
        }

    # ── Apply changes ─────────────────────────────────────────────────────────
    applied = []
    failed = []
    for pending in all_pending:
        ok, err = apply_change(pending["adset_id"], pending["payload"])
        if ok:
            applied.append({"name": pending["name"], "action": pending["action"],
                             "reason": pending["reason"]})
        else:
            failed.append({"name": pending["name"], "action": pending["action"], "error": err})

    return {
        "status": "success",
        "action_taken": action,
        "applied": applied,
        "failed": failed,
        "adset_analysis": adset_data,
        "message": (
            f"Applied {len(applied)} optimization(s): "
            f"{sum(1 for a in applied if a['action'] == 'pause')} paused, "
            f"{sum(1 for a in applied if a['action'] == 'scale')} scaled."
            + (f" {len(failed)} failed." if failed else "")
        ),
    }
