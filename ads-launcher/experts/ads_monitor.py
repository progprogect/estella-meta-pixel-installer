import time
import requests
import json
import os
import sys

API_TOKEN = "{{api_token}}"
META_TOKEN = "{{meta_token}}"
CAMPAIGN_ID = "{{campaign_id}}"
ADSET_IDS = json.loads('{{adset_ids_json}}')
CONVERSION_GOAL = "{{conversion_goal}}"
TARGET_CPA = float("{{target_cpa}}" or "0")
BASE_URL = "{{base_url}}"
INTERVAL_SEC = 21600  # 6 hours

META_VER = "v25.0"

GOAL_ACTION_MAP = {
    "purchase": "offsite_conversion.fb_pixel_purchase",
    "lead": "offsite_conversion.fb_pixel_lead",
    "complete_registration": "offsite_conversion.fb_pixel_complete_registration",
    "app_install": "mobile_app_install",
}
ACTION_TYPE = GOAL_ACTION_MAP.get(CONVERSION_GOAL, "offsite_conversion.fb_pixel_purchase")

EXT_HEADERS = {
    "X-Auth-Token": API_TOKEN,
    "Content-Type": "application/json",
    "X-Profile-Id": "default",
    "X-Agent-Id": "agent_extella_default",
}

start_ts = int(time.time())
last_daily_report_ts = 0
final_report_sent = False
total_conversions_all_time = 0


def kv_get(key):
    try:
        r = requests.get(
            f"{BASE_URL}/api/kv/get",
            headers=EXT_HEADERS,
            params={"key": key},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("value")
    except Exception:
        pass
    return None


def kv_set(key, value):
    try:
        requests.post(
            f"{BASE_URL}/api/kv/set",
            headers=EXT_HEADERS,
            json={"key": key, "value": str(value)},
            timeout=10,
        )
    except Exception:
        pass


def run_expert(expert_name, params):
    try:
        resp = requests.post(
            f"{BASE_URL}/api/expert/run",
            headers=EXT_HEADERS,
            json={"expert_name": expert_name, "params": params, "timeout": 120},
            timeout=135,
        )
        if resp.status_code == 200:
            return resp.json().get("result", {})
    except Exception as e:
        print(f"[monitor] run_expert error ({expert_name}): {e}", flush=True)
    return {}


def get_adset_learning(adset_id):
    try:
        r = requests.get(
            f"https://graph.facebook.com/{META_VER}/{adset_id}",
            params={
                "fields": "name,learning_stage_info,effective_status",
                "access_token": META_TOKEN,
            },
            timeout=20,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def get_campaign_insights():
    try:
        r = requests.get(
            f"https://graph.facebook.com/{META_VER}/{CAMPAIGN_ID}/insights",
            params={
                "fields": "spend,impressions,clicks,reach,frequency,cpm,cpc,ctr,"
                          "actions,action_values,cost_per_action_type",
                "date_preset": "last_7d",
                "access_token": META_TOKEN,
            },
            timeout=20,
        )
        if r.status_code == 200:
            data = r.json().get("data", [])
            return data[0] if data else {}
    except Exception:
        pass
    return {}


def parse_conversions(insights_data):
    for action in insights_data.get("actions", []):
        if action.get("action_type") == ACTION_TYPE:
            try:
                return int(float(action.get("value", 0)))
            except (ValueError, TypeError):
                pass
    return 0


def check_and_report():
    global last_daily_report_ts, final_report_sent, total_conversions_all_time

    print(f"[monitor] === Polling cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ===", flush=True)

    # ── Collect adset learning data ───────────────────────────────────────────
    adset_data = []
    has_fail = False
    for adset_id in ADSET_IDS:
        adset_info = get_adset_learning(adset_id)
        learning = adset_info.get("learning_stage_info", {})
        status = learning.get("status") if learning else None
        conv_window = int(learning.get("conversions", 0)) if learning else 0
        adset_data.append({
            "adset_id": adset_id,
            "name": adset_info.get("name", adset_id),
            "effective_status": adset_info.get("effective_status", "UNKNOWN"),
            "learning_status": status,
            "conversions_in_window": conv_window,
        })
        if status == "FAIL":
            has_fail = True

    # ── Campaign-level insights ───────────────────────────────────────────────
    insights = get_campaign_insights()
    total_conversions = parse_conversions(insights)
    spend = float(insights.get("spend", 0))
    impressions = int(insights.get("impressions", 0))
    ctr = float(insights.get("ctr", 0))
    cpc = float(insights.get("cpc", 0))

    total_conversions_all_time = max(total_conversions_all_time, total_conversions)
    days_running = (int(time.time()) - start_ts) / 86400

    cpa = (spend / total_conversions) if total_conversions > 0 else 0.0

    # ── Save state to KV ──────────────────────────────────────────────────────
    state = {
        "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
        "days_running": round(days_running, 1),
        "total_conversions_7d": total_conversions,
        "total_conversions_all_time": total_conversions_all_time,
        "spend_7d": spend,
        "cpa": round(cpa, 2),
        "impressions_7d": impressions,
        "ctr": round(ctr, 2),
        "cpc": round(cpc, 2),
        "adsets": adset_data,
        "has_learning_fail": has_fail,
    }
    kv_set("ads_monitor_state", json.dumps(state))
    print(f"[monitor] State: {total_conversions} conv (7d), ${spend:.2f} spend, {days_running:.1f}d", flush=True)

    # ── Milestone checks ──────────────────────────────────────────────────────
    params_base = {
        "api_token": API_TOKEN,
        "base_url": BASE_URL,
        "meta_token": META_TOKEN,
        "campaign_id": CAMPAIGN_ID,
        "adset_ids_json": json.dumps(ADSET_IDS),
        "conversion_goal": CONVERSION_GOAL,
        "target_cpa": str(TARGET_CPA),
    }

    if not final_report_sent and (
        total_conversions_all_time >= 100 or days_running >= 7.0
    ):
        print("[monitor] Milestone: triggering final report...", flush=True)
        run_expert("ads_report_final", params_base)
        final_report_sent = True
        kv_set("ads_monitor_final_sent", "1")
        return

    now_ts = int(time.time())
    if now_ts - last_daily_report_ts >= 86400:
        print("[monitor] Triggering daily report...", flush=True)
        run_expert("ads_report_daily", params_base)
        last_daily_report_ts = now_ts
        kv_set("ads_monitor_last_daily_ts", str(now_ts))

    if has_fail:
        print("[monitor] Learning FAIL detected — notifying optimizer...", flush=True)
        run_expert("ads_optimizer", {**params_base, "action": "auto"})


# ── Main loop ─────────────────────────────────────────────────────────────────
print(f"[monitor] Starting. Campaign: {CAMPAIGN_ID}, AdSets: {ADSET_IDS}", flush=True)
print(f"[monitor] Poll interval: {INTERVAL_SEC}s ({INTERVAL_SEC//3600}h)", flush=True)

while True:
    try:
        check_and_report()
    except Exception as e:
        print(f"[monitor] Cycle error: {e}", flush=True)
        kv_set("ads_monitor_error", str(e))

    if final_report_sent:
        print("[monitor] Final report sent. Daemon exiting.", flush=True)
        sys.exit(0)

    time.sleep(INTERVAL_SEC)
