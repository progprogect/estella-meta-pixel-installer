$extens("include.py")
include("import requests", ["extella-pip install requests"])

def ads_intake(
    # Required inputs
    product_info: str = "",
    audience_desc: str = "",
    budget_daily: str = "",
    conversion_goal: str = "",
    ad_account_id: str = "",
    meta_token: str = "",
    # Optional inputs
    offers: str = "",
    git_repo_url: str = "",
    pixel_id: str = "",
    capi_token: str = "",
    target_cpa: str = "",
    creatives: str = "",
    page_id: str = "",
    # Extella infra
    api_token: str = "",
    base_url: str = "https://api.extella.ai",
) -> dict:
    import requests

    REQUIRED = {
        "product_info": product_info,
        "audience_desc": audience_desc,
        "budget_daily": budget_daily,
        "conversion_goal": conversion_goal,
        "ad_account_id": ad_account_id,
        "meta_token": meta_token,
    }
    VALID_GOALS = {"purchase", "lead", "complete_registration", "app_install"}

    # ── Validation ────────────────────────────────────────────────────────────
    missing = [k for k, v in REQUIRED.items() if not str(v).strip()]
    if missing:
        return {
            "status": "needs_input",
            "missing": missing,
            "message": f"Please provide: {', '.join(missing)}",
        }

    goal = conversion_goal.strip().lower()
    if goal not in VALID_GOALS:
        return {
            "status": "needs_input",
            "missing": ["conversion_goal"],
            "message": (
                f"conversion_goal must be one of: {', '.join(VALID_GOALS)}. "
                f"Got: '{conversion_goal}'"
            ),
        }

    try:
        budget = float(str(budget_daily).replace("$", "").replace(",", "").strip())
    except ValueError:
        return {
            "status": "needs_input",
            "missing": ["budget_daily"],
            "message": f"budget_daily must be a number (e.g. 50). Got: '{budget_daily}'",
        }

    if budget < 5:
        return {
            "status": "needs_input",
            "missing": ["budget_daily"],
            "message": f"Minimum daily budget is $5. Got: ${budget}",
        }

    acc = ad_account_id.strip()
    if not acc.startswith("act_"):
        acc = f"act_{acc}"

    # ── KV Save helper ────────────────────────────────────────────────────────
    headers = {
        "X-Auth-Token": api_token,
        "Content-Type": "application/json",
        "X-Profile-Id": "default",
        "X-Agent-Id": "agent_extella_default",
    }

    def kv_set(key: str, value: str) -> bool:
        try:
            r = requests.post(
                f"{base_url}/api/kv/set",
                headers=headers,
                json={"key": key, "value": value},
                timeout=10,
            )
            return r.status_code == 200
        except Exception:
            return False

    kv_data = {
        "ads_product_info": product_info.strip(),
        "ads_audience_desc": audience_desc.strip(),
        "ads_offers": offers.strip(),
        "ads_budget_daily": str(budget),
        "ads_conversion_goal": goal,
        "ads_ad_account_id": acc,
        "ads_meta_token": meta_token.strip(),
    }
    if git_repo_url.strip():
        kv_data["ads_git_repo_url"] = git_repo_url.strip()
    if pixel_id.strip():
        kv_data["ads_pixel_id"] = pixel_id.strip()
    if capi_token.strip():
        kv_data["ads_capi_token"] = capi_token.strip()
    if target_cpa.strip():
        try:
            kv_data["ads_target_cpa"] = str(float(target_cpa.replace("$", "").strip()))
        except ValueError:
            pass
    if creatives.strip():
        kv_data["ads_creatives"] = creatives.strip()
    if page_id.strip():
        kv_data["ads_page_id"] = page_id.strip()

    saved_keys = []
    failed_keys = []
    for key, value in kv_data.items():
        if kv_set(key, value):
            saved_keys.append(key)
        else:
            failed_keys.append(key)

    # ── Build checklist ───────────────────────────────────────────────────────
    checklist = {
        "product_info": bool(product_info.strip()),
        "audience_desc": bool(audience_desc.strip()),
        "budget_daily": True,
        "conversion_goal": True,
        "ad_account_id": True,
        "meta_token": bool(meta_token.strip()),
        "pixel_id": bool(pixel_id.strip()),
        "capi_token": bool(capi_token.strip()),
        "git_repo_url": bool(git_repo_url.strip()),
        "creatives": bool(creatives.strip()),
        "page_id": bool(page_id.strip()),
        "target_cpa": bool(target_cpa.strip()),
    }

    warnings = []
    if not git_repo_url.strip():
        warnings.append("git_repo_url not provided — CAPI integration will be skipped")
    if not pixel_id.strip():
        warnings.append("pixel_id not provided — a new pixel will need to be created first")
    if not creatives.strip():
        warnings.append("creatives not provided — upload images before campaign creation")
    if not page_id.strip():
        warnings.append("page_id not provided — required for ad creatives (Facebook Page ID)")

    return {
        "status": "ready",
        "saved_keys": saved_keys,
        "failed_keys": failed_keys,
        "checklist": checklist,
        "validated": {
            "ad_account_id": acc,
            "budget_daily_usd": budget,
            "conversion_goal": goal,
        },
        "warnings": warnings,
        "message": (
            f"All required inputs validated and saved. "
            f"Budget: ${budget}/day, Goal: {goal}, Account: {acc}."
            + (f" Warnings: {len(warnings)}" if warnings else "")
        ),
    }
