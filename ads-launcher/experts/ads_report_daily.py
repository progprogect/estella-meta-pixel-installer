$extens("include.py")
include("import requests", ["extella-pip install requests"])

def ads_report_daily(
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

    def get_insights(obj_id, level="campaign", date_preset="today"):
        try:
            r = requests.get(
                f"https://graph.facebook.com/{META_VER}/{obj_id}/insights",
                params={
                    "fields": "spend,impressions,clicks,reach,frequency,cpm,cpc,ctr,"
                              "actions,action_values,cost_per_action_type",
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
        cpm = float(data.get("cpm", 0))
        cpc = float(data.get("cpc", 0))
        ctr = float(data.get("ctr", 0))
        cpa = spend / conversions if conversions > 0 else 0.0
        roas = conv_value / spend if spend > 0 else 0.0
        return {
            "spend": spend, "impressions": impressions, "clicks": clicks,
            "reach": reach, "frequency": freq, "cpm": cpm, "cpc": cpc,
            "ctr": ctr, "conversions": conversions, "cpa": cpa, "roas": roas,
        }

    def get_learning(adset_id):
        try:
            r = requests.get(
                f"https://graph.facebook.com/{META_VER}/{adset_id}",
                params={
                    "fields": "name,learning_stage_info,effective_status",
                    "access_token": meta_token,
                },
                timeout=15,
            )
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def recommend(metrics, adset_name, learning_status):
        cpa = metrics["cpa"]
        spend = metrics["spend"]
        conv = metrics["conversions"]
        if learning_status == "FAIL":
            return f"⚠️  PAUSE {adset_name}: learning phase failed. Increase budget or broaden targeting."
        if learning_status == "LEARNING":
            return f"⏳ {adset_name}: still learning ({conv} events so far). Do not change settings."
        if t_cpa > 0 and cpa > t_cpa * 2 and spend > 50:
            return f"🔴 PAUSE {adset_name}: CPA ${cpa:.2f} is {cpa/t_cpa:.1f}x target."
        if t_cpa > 0 and cpa < t_cpa * 0.8 and conv >= 10:
            return f"🟢 SCALE {adset_name}: CPA ${cpa:.2f} is below target — increase budget by 20%."
        if conv == 0 and spend > 50:
            return f"🔴 PAUSE {adset_name}: ${spend:.0f} spent with 0 conversions."
        return f"✅ {adset_name}: within target. Continue monitoring."

    # ── Collect data ──────────────────────────────────────────────────────────
    campaign_insights = get_insights(campaign_id, date_preset="today")
    campaign_metrics = parse_metrics(campaign_insights)
    campaign_name = campaign_id

    adset_rows = []
    recommendations = []
    total_events_window = 0

    for adset_id in adset_ids:
        adset_info = get_learning(adset_id)
        adset_insights = get_insights(adset_id, date_preset="today")
        adset_metrics = parse_metrics(adset_insights)
        learning = adset_info.get("learning_stage_info", {})
        learning_status = learning.get("status") if learning else None
        events_window = int(learning.get("conversions", 0)) if learning else 0
        total_events_window += events_window
        adset_name = adset_info.get("name", adset_id)

        adset_rows.append({
            "name": adset_name,
            "spend": adset_metrics["spend"],
            "conversions": adset_metrics["conversions"],
            "cpa": adset_metrics["cpa"],
            "learning_status": learning_status or "N/A",
            "events_window": events_window,
        })
        rec = recommend(adset_metrics, adset_name, learning_status)
        recommendations.append(rec)

    # ── Format report ─────────────────────────────────────────────────────────
    date_str = time.strftime("%Y-%m-%d")
    m = campaign_metrics

    rows_txt = ""
    for row in adset_rows:
        ls = row["learning_status"] or "N/A"
        rows_txt += (
            f"  {row['name'][:28]:<28} | ${row['spend']:>7.2f} | "
            f"{row['conversions']:>5} | ${row['cpa']:>7.2f} | {ls}\n"
        )

    recs_txt = "\n  ".join(recommendations) if recommendations else "No recommendations."
    target_txt = f" (target: ${t_cpa:.2f})" if t_cpa > 0 else ""

    report_text = f"""
DAILY PERFORMANCE REPORT — {date_str}
Campaign: {campaign_id}
{'='*60}

OVERVIEW (today):
  Spend:       ${m['spend']:.2f}
  Impressions: {m['impressions']:,} (Reach: {m['reach']:,}, Frequency: {m['frequency']:.1f}x)
  Clicks:      {m['clicks']:,} (CTR: {m['ctr']:.2f}%)
  Conversions: {m['conversions']}
  CPA:         ${m['cpa']:.2f}{target_txt}
  ROAS:        {m['roas']:.1f}x

AD SET BREAKDOWN:
  {'Ad Set':<28} | {'Spend':>8} | {'Conv.':>6} | {'CPA':>8} | Learning
  {'-'*28}-+-{'-'*8}-+-{'-'*6}-+-{'-'*8}-+------------
{rows_txt}
PIXEL LEARNING:
  Total events this week: {total_events_window} / 50 (learning exit)
  Progress to 100 events goal: {total_events_window} / 100

RECOMMENDATIONS:
  {recs_txt}

Next check in 6 hours.
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
            json={"key": "ads_last_daily_report", "value": report_text},
            timeout=10,
        )
    except Exception:
        pass

    return {
        "status": "success",
        "report_date": date_str,
        "report_text": report_text,
        "campaign_metrics": campaign_metrics,
        "adset_rows": adset_rows,
        "recommendations": recommendations,
        "message": f"Daily report for {date_str}: {m['conversions']} conversions, ${m['spend']:.2f} spend.",
    }
