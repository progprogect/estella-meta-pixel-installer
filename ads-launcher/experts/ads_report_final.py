$extens("include.py")
include("import requests", ["extella-pip install requests"])

def ads_report_final(
    campaign_id: str = "",
    adset_ids_json: str = "[]",
    conversion_goal: str = "purchase",
    target_cpa: str = "0",
    meta_token: str = "",
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

    def get_insights(obj_id, date_preset="last_7d"):
        try:
            r = requests.get(
                f"https://graph.facebook.com/{META_VER}/{obj_id}/insights",
                params={
                    "fields": "spend,impressions,clicks,reach,frequency,cpm,cpc,ctr,"
                              "actions,action_values,cost_per_action_type,date_start,date_stop",
                    "date_preset": date_preset,
                    "access_token": meta_token,
                },
                timeout=20,
            )
            if r.status_code == 200:
                data = r.json().get("data", [])
                return data[0] if data else {}
        except Exception:
            pass
        return {}

    def parse_metrics(data):
        conversions = 0
        conv_value = 0.0
        for a in data.get("actions", []):
            if a.get("action_type") == action_type:
                try:
                    conversions += int(float(a.get("value", 0)))
                except (ValueError, TypeError):
                    pass
        for av in data.get("action_values", []):
            if av.get("action_type") == action_type:
                try:
                    conv_value += float(av.get("value", 0))
                except (ValueError, TypeError):
                    pass
        spend = float(data.get("spend", 0))
        impressions = int(data.get("impressions", 0))
        clicks = int(data.get("clicks", 0))
        reach = int(data.get("reach", 0))
        freq = float(data.get("frequency", 0))
        cpc = float(data.get("cpc", 0))
        ctr = float(data.get("ctr", 0))
        cpa = spend / conversions if conversions > 0 else 0.0
        roas = conv_value / spend if spend > 0 else 0.0
        return {
            "spend": spend, "impressions": impressions, "clicks": clicks,
            "reach": reach, "frequency": freq, "cpc": cpc, "ctr": ctr,
            "conversions": conversions, "conv_value": conv_value,
            "cpa": cpa, "roas": roas,
        }

    def get_adset_info(adset_id):
        try:
            r = requests.get(
                f"https://graph.facebook.com/{META_VER}/{adset_id}",
                params={
                    "fields": "name,learning_stage_info,effective_status,created_time",
                    "access_token": meta_token,
                },
                timeout=15,
            )
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    # ── Collect data ──────────────────────────────────────────────────────────
    campaign_insights = get_insights(campaign_id, date_preset="last_7d")
    campaign_metrics = parse_metrics(campaign_insights)

    date_start = campaign_insights.get("date_start", "N/A")
    date_stop = campaign_insights.get("date_stop", time.strftime("%Y-%m-%d"))

    adset_results = []
    for adset_id in adset_ids:
        info = get_adset_info(adset_id)
        adset_insights = get_insights(adset_id, date_preset="last_7d")
        metrics = parse_metrics(adset_insights)
        learning = info.get("learning_stage_info", {})
        learning_status = learning.get("status") if learning else "UNKNOWN"
        conv_window = int(learning.get("conversions", 0)) if learning else 0
        adset_results.append({
            "adset_id": adset_id,
            "name": info.get("name", adset_id),
            "learning_status": learning_status,
            "conversions_in_window": conv_window,
            "metrics": metrics,
        })

    adset_results.sort(key=lambda x: (x["metrics"]["cpa"] if x["metrics"]["cpa"] > 0 else 9999))

    m = campaign_metrics
    total_events_window = sum(a["conversions_in_window"] for a in adset_results)
    learning_complete = total_events_window >= 50

    # ── Build scaling recommendations ─────────────────────────────────────────
    scale_recs = []
    pause_recs = []
    for i, adset in enumerate(adset_results):
        am = adset["metrics"]
        name = adset["name"]
        cpa = am["cpa"]
        spend = am["spend"]
        conv = am["conversions"]
        ls = adset["learning_status"]

        if ls == "FAIL" or (t_cpa > 0 and cpa > t_cpa * 2 and spend > 30) or (conv == 0 and spend > 50):
            pause_recs.append(f"❌ PAUSE '{name}': "
                              + (f"CPA ${cpa:.2f} ({cpa/t_cpa:.1f}x target)" if t_cpa > 0 and cpa > 0 else
                                 "learning failed or no conversions"))
        elif t_cpa > 0 and cpa < t_cpa * 0.8 and conv >= 10:
            scale_recs.append(f"✅ SCALE '{name}': CPA ${cpa:.2f} — increase budget by 20%")

    # ── Format final report ───────────────────────────────────────────────────
    target_txt = f" (target: ${t_cpa:.2f})" if t_cpa > 0 else ""

    adset_ranking = ""
    for i, adset in enumerate(adset_results):
        am = adset["metrics"]
        rank_icon = "🥇" if i == 0 else ("🥈" if i == 1 else "🥉")
        adset_ranking += (
            f"  {rank_icon} {adset['name'][:35]}: "
            f"${am['spend']:.2f} spend, {am['conversions']} conv, "
            f"${am['cpa']:.2f} CPA, {am['roas']:.1f}x ROAS "
            f"[{adset['learning_status'] or 'N/A'}]\n"
        )

    all_recs = scale_recs + pause_recs
    if not all_recs:
        all_recs = ["All ad sets within target range. Continue running."]
    recs_txt = "\n  ".join(all_recs)

    learning_txt = "✅ COMPLETED" if learning_complete else (
        f"⏳ IN PROGRESS ({total_events_window}/50 events this week)"
    )

    report_text = f"""
FINAL CAMPAIGN REPORT
{'='*60}
Campaign: {campaign_id}
Period: {date_start} — {date_stop}

CAMPAIGN SUMMARY:
  Total Spend:       ${m['spend']:.2f}
  Total Conversions: {m['conversions']}
  Overall CPA:       ${m['cpa']:.2f}{target_txt}
  Overall ROAS:      {m['roas']:.1f}x
  Impressions:       {m['impressions']:,} (Reach: {m['reach']:,})
  CTR:               {m['ctr']:.2f}% | CPC: ${m['cpc']:.2f}

PIXEL LEARNING:
  Status:           {learning_txt}
  Events this week: {total_events_window} / 50 (learning threshold)

AD SET PERFORMANCE (ranked by CPA):
{adset_ranking}
SCALING RECOMMENDATIONS:
  {recs_txt}

NEXT STEPS:
  1. Merge or close underperforming ad sets per recommendations above
  2. Scale winning ad sets by +20% budget increments (max every 3 days)
  3. Refresh creative for ad sets with frequency > 3.0
  4. Consider duplicating top ad set with broader audience (Lookalike 2-3%)
  5. Enable Advantage+ placement if you restricted placements earlier

CAPI & PIXEL:
  Verify event match quality in Meta Events Manager → Data Sources
  Target EMQ score: 7+/10 for reliable conversion tracking
{'='*60}
""".strip()

    # ── Save report to KV ─────────────────────────────────────────────────────
    try:
        requests.post(
            f"{base_url}/api/kv/set",
            headers={
                "X-Auth-Token": api_token,
                "Content-Type": "application/json",
                "X-Profile-Id": "default",
                "X-Agent-Id": "agent_extella_default",
            },
            json={"key": "ads_final_report", "value": report_text},
            timeout=10,
        )
    except Exception:
        pass

    return {
        "status": "success",
        "report_period": f"{date_start} — {date_stop}",
        "report_text": report_text,
        "campaign_metrics": campaign_metrics,
        "adset_rankings": [
            {"name": a["name"], "cpa": a["metrics"]["cpa"],
             "conversions": a["metrics"]["conversions"],
             "learning_status": a["learning_status"]}
            for a in adset_results
        ],
        "scale_recommendations": scale_recs,
        "pause_recommendations": pause_recs,
        "learning_complete": learning_complete,
        "message": (
            f"Final report: {m['conversions']} total conversions, "
            f"${m['spend']:.2f} spent, ${m['cpa']:.2f} CPA, {m['roas']:.1f}x ROAS."
        ),
    }
