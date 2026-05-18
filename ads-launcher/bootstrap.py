"""
bootstrap.py — Publishes the Meta Ads Launcher preset to Extella API.
Publishes all concepts under ads-launcher/concepts/ and all experts in EXPERT_META.

Usage:
    python3 bootstrap.py
    python3 bootstrap.py --dry-run                 # print only, no API calls
    python3 bootstrap.py --sync-concept-registry   # fill ads-launcher/concept_registry.json from /api/concept/list, then exit

Concept updates:
    If ads-launcher/concept_registry.json maps a file path to concept_id, POST /api/concept/update is used.
    Otherwise POST /api/concept/add runs and the new id is written to the registry.
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

# ─── Config ──────────────────────────────────────────────────────────────────

API_TOKEN = os.environ.get("EXTELLA_TOKEN", "")
BASE_URL  = os.environ.get("EXTELLA_URL", "https://api.extella.ai")
DRY_RUN   = "--dry-run" in sys.argv
SYNC_ONLY = "--sync-concept-registry" in sys.argv

PRESET_DIR = Path(__file__).parent
CONCEPTS_DIR = PRESET_DIR / "concepts"
EXPERTS_DIR  = PRESET_DIR / "experts"
CONCEPT_REGISTRY_PATH = PRESET_DIR / "concept_registry.json"

HEADERS = {
    "X-Auth-Token": API_TOKEN,
    "Content-Type": "application/json",
    "X-Profile-Id": "default",
    "X-Agent-Id": "agent_extella_default",
}

# ─── Concept registry (update vs add) ───────────────────────────────────────

def load_concept_registry():
    if not CONCEPT_REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(CONCEPT_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_concept_registry(reg: dict):
    CONCEPT_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONCEPT_REGISTRY_PATH.write_text(
        json.dumps(reg, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def first_concept_heading_line(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("##"):
            return s[:320]
    return ""


def flatten_concept_list(payload) -> list:
    if not isinstance(payload, dict):
        return []
    for key in ("concepts", "results", "data", "items", "list"):
        v = payload.get(key)
        if isinstance(v, list):
            return v
    return []


def concept_item_id(item: dict):
    for k in ("concept_id", "id", "conceptId"):
        v = item.get(k)
        if v is not None and str(v).isdigit():
            return int(v)
    return None


def concept_item_text(item: dict) -> str:
    return item.get("text") or item.get("concept_text") or item.get("new_text") or ""


# ─── Helpers ─────────────────────────────────────────────────────────────────

def api_post(path, payload):
    if DRY_RUN:
        print(f"  [DRY-RUN] POST {path}")
        return {"status": "success", "id": 0, "expert_name": payload.get("name", "")}
    resp = requests.post(f"{BASE_URL}{path}", headers=HEADERS, json=payload, timeout=30)
    return resp.json()

def read_file(path):
    return Path(path).read_text(encoding="utf-8")

def color(text, code):
    return f"\033[{code}m{text}\033[0m"

OK  = color("✓", "32")
ERR = color("✗", "31")
INF = color("→", "36")


def sync_concept_registry_from_remote():
    """Match local concept files to remote concepts by first ## heading line; write concept_registry.json."""
    print(f"\n{color('SYNC CONCEPT REGISTRY', '1;36')}  ←  POST /api/concept/list\n")

    data = api_post("/api/concept/list", {})
    items = flatten_concept_list(data)
    if not items:
        print(f"{ERR} No concepts in API response or unexpected shape: {str(data)[:500]}")
        return False

    reg = {}
    matched = 0
    ambiguous = 0

    for cf in sorted(CONCEPTS_DIR.glob("*.txt")):
        rel_key = str(cf.relative_to(PRESET_DIR))
        local_text = read_file(cf)
        fp = first_concept_heading_line(local_text)
        if not fp:
            print(f"{ERR} {rel_key}: no ## heading — cannot fingerprint")
            continue

        hits = []
        for it in items:
            if not isinstance(it, dict):
                continue
            remote_text = concept_item_text(it)
            rp = first_concept_heading_line(remote_text)
            if fp == rp and fp:
                cid = concept_item_id(it)
                if cid is not None:
                    hits.append((cid, it))

        if not hits:
            print(f"{INF} {rel_key}: no remote match for heading {fp[:60]}...")
            continue
        hits.sort(key=lambda x: x[0], reverse=True)
        best_id = hits[0][0]
        if len(hits) > 1:
            ambiguous += 1
            print(f"{INF} {rel_key}: multiple matches ({len(hits)}), using highest concept_id={best_id}")

        reg[rel_key] = best_id
        matched += 1
        print(f"  {OK} {rel_key} → concept_id {best_id}")

    if matched == 0:
        print(f"\n{ERR} No matches — registry not written. Check API response shape or remote concepts.")
        return False

    save_concept_registry(reg)
    print(f"\n{color(f'Matched {matched} files; wrote {CONCEPT_REGISTRY_PATH}', '32')}")
    if ambiguous:
        print(f"{color(f'Note: {ambiguous} files had multiple remote matches (used newest id).', '33')}")
    return matched > 0

# ─── Expert Metadata ─────────────────────────────────────────────────────────

EXPERT_META = {
    "ads_intake": {
        "name": "ads_intake",
        "description": (
            "Validates and structures all user inputs for the Meta Ads Launcher preset. "
            "Saves all provided data to KV Store keys (ads_product_info, ads_audience_desc, "
            "ads_offers, ads_budget_daily, ads_conversion_goal, ads_ad_account_id, ads_meta_token, etc.). "
            "Returns {status: 'ready'} if all required fields are present and valid, "
            "or {status: 'needs_input', missing: [...]} if any required inputs are absent. "
            "Required: product_info, audience_desc, budget_daily, conversion_goal, ad_account_id, meta_token. "
            "Optional: offers, git_repo_url, pixel_id, capi_token, target_cpa, creatives, page_id."
        ),
        "kwargs": {
            "product_info": "",
            "audience_desc": "",
            "budget_daily": "",
            "conversion_goal": "",
            "ad_account_id": "",
            "meta_token": "",
            "offers": "",
            "git_repo_url": "",
            "pixel_id": "",
            "capi_token": "",
            "target_cpa": "",
            "creatives": "",
            "page_id": "",
            "api_token": "",
            "base_url": "https://api.extella.ai",
        },
        "cspl": "fython",
        "file": "ads_intake.py",
    },
    "ads_git_clone": {
        "name": "ads_git_clone",
        "description": (
            "Clones a Git repository to a local destination directory. "
            "Shell CSPL expert — runs as a bash command with template placeholders. "
            "MUST run locally (target=device_uuid). "
            "Parameters: repo_url — Git repository URL (SSH or HTTPS); "
            "dest_dir — absolute local path to clone into."
        ),
        "kwargs": {
            "repo_url": "",
            "dest_dir": "",
        },
        "cspl": "shell",
        "file": "ads_git_clone.sh",
    },
    "ads_git_commit_push": {
        "name": "ads_git_commit_push",
        "description": (
            "Creates a new Git branch, stages all changes, commits, and pushes to origin. "
            "Shell CSPL expert — runs as a bash command with template placeholders. "
            "MUST run locally (target=device_uuid). "
            "Parameters: repo_dir — absolute path to the cloned repository; "
            "branch — branch name to create (e.g. capi-integration); "
            "commit_msg — commit message string."
        ),
        "kwargs": {
            "repo_dir": "",
            "branch": "",
            "commit_msg": "",
        },
        "cspl": "shell",
        "file": "ads_git_commit_push.sh",
    },
    "ads_capi_git_install": {
        "name": "ads_capi_git_install",
        "description": (
            "Installs Meta Conversions API (CAPI) server-side event tracking into a website repository via Git. "
            "MUST run locally (target=device_uuid). "
            "Steps: 1) calls ads_git_clone to clone the repo; 2) detects the tech stack "
            "(Node.js/Python/PHP from file tree); 3) generates the CAPI integration helper file "
            "appropriate to the stack; 4) writes the file; 5) calls ads_git_commit_push to create "
            "the 'capi-integration' branch and push; 6) optionally creates a GitHub PR via GitHub API. "
            "Returns {status, stack, file_created, branch, pr_url}. "
            "Parameters: repo_url, pixel_id, capi_token, github_token (optional), "
            "api_token, base_url, device_uuid."
        ),
        "kwargs": {
            "repo_url": "",
            "pixel_id": "",
            "capi_token": "",
            "github_token": "",
            "api_token": "",
            "base_url": "https://api.extella.ai",
            "device_uuid": "",
        },
        "cspl": "fython",
        "file": "ads_capi_git_install.py",
    },
    "ads_audience_builder": {
        "name": "ads_audience_builder",
        "description": (
            "Builds three targeting audience segments for Meta Ads campaigns: "
            "Cold (interest-based via AI mapping), Warm (pixel retargeting — website visitors 180d), "
            "and Lookalike (1% similar to converters). "
            "Uses Extella Agents API to map free-text audience descriptions to Meta interest category IDs. "
            "Creates custom audiences via Meta Graph API. "
            "Returns {targeting_specs: [{type, name, targeting_json, description}], audience_summaries}. "
            "Parameters: audience_desc, conversion_goal, pixel_id, ad_account_id, meta_token, "
            "api_token, base_url."
        ),
        "kwargs": {
            "audience_desc": "",
            "conversion_goal": "purchase",
            "pixel_id": "",
            "ad_account_id": "",
            "meta_token": "",
            "api_token": "",
            "base_url": "https://api.extella.ai",
        },
        "cspl": "fython",
        "file": "ads_audience_builder.py",
    },
    "ads_creative_upload": {
        "name": "ads_creative_upload",
        "description": (
            "Uploads ad images to Meta Ads Manager and creates ad creatives with object_story_spec. "
            "Accepts image URLs (downloaded automatically) or base64 strings. "
            "Steps: 1) download/decode image; 2) POST /adimages to get image hash; "
            "3) POST /adcreatives with page_id, message, headline, link, CTA. "
            "Returns {creative_ids, image_hashes, creative_previews}. "
            "Parameters: creatives_json (JSON array of URLs or base64), ad_copy, headline, "
            "link_url, call_to_action, page_id, ad_account_id, meta_token, api_token, base_url."
        ),
        "kwargs": {
            "creatives_json": "",
            "ad_copy": "",
            "headline": "",
            "link_url": "",
            "call_to_action": "LEARN_MORE",
            "page_id": "",
            "ad_account_id": "",
            "meta_token": "",
            "api_token": "",
            "base_url": "https://api.extella.ai",
        },
        "cspl": "fython",
        "file": "ads_creative_upload.py",
    },
    "ads_adset_worker": {
        "name": "ads_adset_worker",
        "description": (
            "Creates one Meta Ads ad set and its ads. Designed to be called in parallel x3 "
            "by ads_campaign_create via parallel_task CSPL. "
            "Each instance handles: POST /adsets (PAUSED) then POST /ads for each creative. "
            "Returns {adset_id, adset_name, ad_ids, ad_errors}. "
            "Parameters: campaign_id, adset_name, targeting_json, daily_budget_cents, "
            "optimization_goal, billing_event, promoted_object_json, creative_ids_json, "
            "meta_token, ad_account_id, __description__ (for parallel task label)."
        ),
        "kwargs": {
            "campaign_id": "",
            "adset_name": "",
            "targeting_json": "{}",
            "daily_budget_cents": 2000,
            "optimization_goal": "OFFSITE_CONVERSIONS",
            "billing_event": "IMPRESSIONS",
            "promoted_object_json": "{}",
            "creative_ids_json": "[]",
            "meta_token": "",
            "ad_account_id": "",
            "__description__": "",
            "api_token": "",
            "base_url": "https://api.extella.ai",
        },
        "cspl": "parallel_task",
        "file": "ads_adset_worker.py",
    },
    "ads_campaign_create": {
        "name": "ads_campaign_create",
        "description": (
            "Creates a complete Meta Ads campaign structure: 1 Campaign + 3 Ad Sets (Cold/Warm/Lookalike) "
            "+ Ads — all PAUSED, awaiting user confirmation to launch. "
            "Fan-out: launches ads_adset_worker x3 in parallel via parallel_task CSPL, "
            "waits for all via demo_wait_tasks. Saves campaign_id, adset_ids, ad_ids to KV. "
            "Returns {campaign_id, adset_ids, ad_ids, structure_summary}. "
            "Campaign stays PAUSED until ads_optimizer action=unpause is called. "
            "Parameters: campaign_name, pixel_id, conversion_goal, budget_daily, "
            "targeting_specs_json (from ads_audience_builder), creative_ids_json (from ads_creative_upload), "
            "ad_account_id, meta_token, device_uuid, api_token, base_url."
        ),
        "kwargs": {
            "campaign_name": "",
            "pixel_id": "",
            "conversion_goal": "purchase",
            "budget_daily": "50",
            "targeting_specs_json": "[]",
            "creative_ids_json": "[]",
            "ad_account_id": "",
            "meta_token": "",
            "device_uuid": "",
            "api_token": "",
            "base_url": "https://api.extella.ai",
        },
        "cspl": "fython",
        "file": "ads_campaign_create.py",
    },
    "ads_monitor": {
        "name": "ads_monitor",
        "description": (
            "Background monitoring daemon for Meta Ads campaigns. nohup CSPL — runs as detached process. "
            "MUST run locally (target=device_uuid). "
            "Polls Meta Graph API every 6 hours: checks learning_stage_info per ad set and "
            "campaign-level insights (spend, conversions, CPA). "
            "Milestone triggers: 100 conversions or 7 days → ads_report_final; "
            "every 24h → ads_report_daily; learning FAIL → ads_optimizer. "
            "Writes state to KV key ads_monitor_state. Returns {pid, log_file} immediately. "
            "Placeholders: api_token, meta_token, campaign_id, adset_ids_json, "
            "conversion_goal, target_cpa, base_url."
        ),
        "kwargs": {
            "api_token": "",
            "meta_token": "",
            "campaign_id": "",
            "adset_ids_json": "[]",
            "conversion_goal": "purchase",
            "target_cpa": "0",
            "base_url": "https://api.extella.ai",
        },
        "cspl": "nohup",
        "file": "ads_monitor.py",
    },
    "ads_report_daily": {
        "name": "ads_report_daily",
        "description": (
            "Generates a daily performance report for a Meta Ads campaign. "
            "Fetches today's insights from campaign and each ad set via Meta Graph API. "
            "Includes: spend, impressions, CTR, CPC, conversions, CPA, ROAS, frequency, "
            "learning phase status per ad set, and actionable recommendations. "
            "Saves report to KV key ads_last_daily_report. "
            "Returns {report_text, campaign_metrics, adset_rows, recommendations}. "
            "Parameters: campaign_id, adset_ids_json, conversion_goal, target_cpa, "
            "meta_token, api_token, base_url."
        ),
        "kwargs": {
            "campaign_id": "",
            "adset_ids_json": "[]",
            "conversion_goal": "purchase",
            "target_cpa": "0",
            "meta_token": "",
            "api_token": "",
            "base_url": "https://api.extella.ai",
        },
        "cspl": "fython",
        "file": "ads_report_daily.py",
    },
    "ads_report_final": {
        "name": "ads_report_final",
        "description": (
            "Generates a comprehensive final report for a Meta Ads campaign test launch. "
            "Fetches last-7-days insights from campaign and each ad set. "
            "Includes: total spend, conversions, CPA, ROAS, ad set performance ranking, "
            "pixel learning completion status, CAPI status, and scaling/optimization recommendations. "
            "Saves report to KV key ads_final_report. "
            "Triggered automatically by ads_monitor when 100 conversions or 7 days elapsed. "
            "Returns {report_text, campaign_metrics, adset_rankings, scale_recommendations, "
            "pause_recommendations, learning_complete}. "
            "Parameters: campaign_id, adset_ids_json, conversion_goal, target_cpa, "
            "meta_token, api_token, base_url."
        ),
        "kwargs": {
            "campaign_id": "",
            "adset_ids_json": "[]",
            "conversion_goal": "purchase",
            "target_cpa": "0",
            "meta_token": "",
            "api_token": "",
            "base_url": "https://api.extella.ai",
        },
        "cspl": "fython",
        "file": "ads_report_final.py",
    },
    "ads_optimizer": {
        "name": "ads_optimizer",
        "description": (
            "Optimizes Meta Ads campaign budget allocation and ad set activation. "
            "Actions: 'auto' — analyze + apply recommendations; 'pause' — pause underperformers; "
            "'scale' — increase budgets +20% for top performers; 'unpause' — activate all (for launch); "
            "'report' — return recommendations without applying changes. "
            "Without confirm=True, returns {status: 'pending_approval', pending_actions: [...]} "
            "for user review before applying. With confirm=True, applies immediately. "
            "Criteria: pause if CPA > 2x target or $50 spend / 0 conversions or learning FAIL; "
            "scale if CPA < 0.8x target and conversions >= 10. "
            "Returns {applied, failed, adset_analysis}. "
            "Parameters: action, adset_ids_json, campaign_id, conversion_goal, target_cpa, "
            "meta_token, confirm, api_token, base_url."
        ),
        "kwargs": {
            "action": "auto",
            "adset_ids_json": "[]",
            "campaign_id": "",
            "conversion_goal": "purchase",
            "target_cpa": "0",
            "meta_token": "",
            "confirm": False,
            "api_token": "",
            "base_url": "https://api.extella.ai",
        },
        "cspl": "fython",
        "file": "ads_optimizer.py",
    },
    "ads_pipeline": {
        "name": "ads_pipeline",
        "description": (
            "Master orchestrator for the Meta Ads Launcher preset. "
            "Runs the full end-to-end pipeline or individual steps. "
            "Step flow: intake → capi → audience → creative → campaign → launch. "
            "Loads inputs from KV if not passed directly. "
            "Returns 'waiting_for_merge' after CAPI step (user must merge PR); "
            "returns 'awaiting_launch_confirmation' after campaign creation (user must confirm to launch); "
            "returns 'launched' after unpausing + starting monitor daemon. "
            "step parameter: 'all' (full pipeline, pauses at checkpoints), "
            "'intake', 'capi', 'audience', 'creative', 'campaign', 'launch'. "
            "Parameters: product_info, audience_desc, budget_daily, conversion_goal, "
            "ad_account_id, meta_token, pixel_id, page_id, creatives_json, ad_copy, headline, "
            "link_url, call_to_action, target_cpa, git_repo_url, github_token, capi_token, "
            "step, device_uuid, api_token, base_url."
        ),
        "kwargs": {
            "product_info": "",
            "audience_desc": "",
            "budget_daily": "",
            "conversion_goal": "",
            "ad_account_id": "",
            "meta_token": "",
            "pixel_id": "",
            "page_id": "",
            "creatives_json": "",
            "ad_copy": "",
            "headline": "",
            "link_url": "",
            "call_to_action": "LEARN_MORE",
            "target_cpa": "",
            "git_repo_url": "",
            "github_token": "",
            "capi_token": "",
            "step": "all",
            "device_uuid": "",
            "api_token": "",
            "base_url": "https://api.extella.ai",
        },
        "cspl": "fython",
        "file": "ads_pipeline.py",
    },
}

# ─── Publish Concepts ────────────────────────────────────────────────────────

def publish_concepts():
    concept_files = sorted(CONCEPTS_DIR.glob("*.txt"))
    n = len(concept_files)
    reg = load_concept_registry()

    print(f"\n{color('═' * 50, '36')}")
    print(f"{color(f'PUBLISHING CONCEPTS ({n})', '1;36')}")
    print(f"{color('═' * 50, '36')}\n")

    results = []

    for cf in concept_files:
        name = cf.stem
        rel_key = str(cf.relative_to(PRESET_DIR))
        text = read_file(cf)
        print(f"{INF} Concept: {name}")

        existing_id = reg.get(rel_key)
        if existing_id is not None:
            try:
                existing_id = int(existing_id)
            except (TypeError, ValueError):
                existing_id = None

        if existing_id:
            resp = api_post("/api/concept/update", {"concept_id": existing_id, "new_text": text})
            if resp.get("status") == "success":
                print(f"  {OK} Updated  →  concept_id: {existing_id}")
                results.append({"name": name, "id": existing_id, "status": "ok", "action": "update"})
            else:
                print(f"  {ERR} Update failed: {resp}")
                results.append({"name": name, "status": "error", "response": str(resp), "action": "update"})
        else:
            resp = api_post("/api/concept/add", {"text": text})
            if resp.get("status") == "success":
                concept_id = resp.get("id")
                print(f"  {OK} Added  →  concept_id: {concept_id}")
                results.append({"name": name, "id": concept_id, "status": "ok", "action": "add"})
                if concept_id is not None and not DRY_RUN:
                    reg[rel_key] = int(concept_id)
                    save_concept_registry(reg)
            else:
                print(f"  {ERR} Add failed: {resp}")
                results.append({"name": name, "status": "error", "response": str(resp), "action": "add"})

        if not DRY_RUN:
            time.sleep(0.3)

    return results

# ─── Publish Experts ─────────────────────────────────────────────────────────

def publish_experts():
    n_experts = len(EXPERT_META)
    print(f"\n{color('═' * 50, '36')}")
    print(f"{color(f'PUBLISHING EXPERTS ({n_experts})', '1;36')}")
    print(f"{color('═' * 50, '36')}\n")

    results = []

    for expert_key, meta in EXPERT_META.items():
        code_path = EXPERTS_DIR / meta["file"]
        if not code_path.exists():
            print(f"  {ERR} File not found: {code_path}")
            results.append({"name": meta["name"], "status": "error", "reason": "file_not_found"})
            continue

        code = read_file(code_path)
        print(f"{INF} Expert: {meta['name']} (cspl={meta['cspl']})")

        payload = {
            "name": meta["name"],
            "description": meta["description"],
            "code": code,
            "kwargs": meta["kwargs"],
            "cspl": meta["cspl"],
        }

        resp = api_post("/api/expert/save", payload)

        if resp.get("status") == "success":
            print(f"  {OK} Saved  →  {resp.get('expert_name', meta['name'])}")
            results.append({"name": meta["name"], "status": "ok"})
        else:
            print(f"  {ERR} Failed: {resp}")
            results.append({"name": meta["name"], "status": "error", "response": str(resp)})

        if not DRY_RUN:
            time.sleep(0.3)

    return results

# ─── Print Summary ────────────────────────────────────────────────────────────

def print_summary(concept_results, expert_results):
    print(f"\n{color('═' * 50, '36')}")
    print(f"{color('SUMMARY', '1;36')}")
    print(f"{color('═' * 50, '36')}\n")

    c_ok  = sum(1 for r in concept_results if r["status"] == "ok")
    c_err = sum(1 for r in concept_results if r["status"] == "error")
    e_ok  = sum(1 for r in expert_results  if r["status"] == "ok")
    e_err = sum(1 for r in expert_results  if r["status"] == "error")

    print(f"  Concepts:  {color(str(c_ok) + ' published', '32')}  /  {color(str(c_err) + ' failed', '31') if c_err else '0 failed'}")
    print(f"  Experts:   {color(str(e_ok) + ' saved',    '32')}  /  {color(str(e_err) + ' failed', '31') if e_err else '0 failed'}")

    if c_err == 0 and e_err == 0:
        print(f"\n{color('✅ Ads Launcher preset published successfully!', '1;32')}")
    else:
        print(f"\n{color('⚠️  Some items failed. Check errors above.', '1;33')}")

    print(f"\n{color('Next steps:', '1;36')}")
    print("  1. Set KV keys in Extella:")
    print("       extella_device_uuid — from Extella Desktop → Settings")
    print("       ads_meta_token      — Graph API token with ads_management scope")
    print("       ads_ad_account_id   — your Meta ad account ID (act_XXXXXXXXXX)")
    print("       ads_pixel_id        — Meta Pixel ID (from pixel-installer preset)")
    print("       ads_page_id         — Facebook Page ID (required for ad creatives)")
    print("  2. In Extella chat, invoke the master concept: 01_ads_launcher_guide")
    print("  3. Follow the guide — provide product info, audience, budget, and creatives.")
    print("     The agent will guide you through each step automatically.")
    print()

# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{color('META ADS LAUNCHER — Preset Bootstrap', '1;35')}")
    print(f"  API: {BASE_URL}")
    if API_TOKEN and len(API_TOKEN) >= 12:
        print(f"  Token: {API_TOKEN[:8]}...{API_TOKEN[-4:]}")
    else:
        print(f"  Token: {color('(set EXTELLA_TOKEN)', '33')}")

    if not DRY_RUN and not (API_TOKEN or "").strip():
        print(f"\n{ERR} EXTELLA_TOKEN is not set. Export it before running bootstrap.")
        sys.exit(1)

    if DRY_RUN:
        print(f"  {color('DRY RUN MODE — no API calls will be made', '1;33')}")

    if SYNC_ONLY:
        if DRY_RUN:
            print(f"{ERR} --sync-concept-registry cannot be combined with --dry-run")
            sys.exit(1)
        try:
            val = requests.post(f"{BASE_URL}/api/token/validate",
                headers=HEADERS,
                json={"token": API_TOKEN}, timeout=10)
            vdata = val.json()
            if not vdata.get("valid"):
                print(f"{ERR} Token invalid: {vdata}")
                sys.exit(1)
            print(f"  {OK} Token valid — user_id: {vdata.get('user_id', '?')}")
        except Exception as e:
            print(f"{ERR} Token validation failed: {e}")
            sys.exit(1)
        ok = sync_concept_registry_from_remote()
        sys.exit(0 if ok else 1)

    # Validate token
    if not DRY_RUN:
        try:
            val = requests.post(f"{BASE_URL}/api/token/validate",
                headers=HEADERS,
                json={"token": API_TOKEN}, timeout=10)
            vdata = val.json()
            if not vdata.get("valid"):
                print(f"{ERR} Token invalid: {vdata}")
                sys.exit(1)
            print(f"  {OK} Token valid — user_id: {vdata.get('user_id', '?')}")
        except Exception as e:
            print(f"{ERR} Token validation failed: {e}")
            sys.exit(1)

    concept_results = publish_concepts()
    expert_results  = publish_experts()
    print_summary(concept_results, expert_results)
