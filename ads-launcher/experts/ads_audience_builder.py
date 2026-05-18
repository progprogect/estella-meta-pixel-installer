$extens("include.py")
include("import requests", ["extella-pip install requests"])

def ads_audience_builder(
    audience_desc: str = "",
    conversion_goal: str = "purchase",
    pixel_id: str = "",
    ad_account_id: str = "",
    meta_token: str = "",
    api_token: str = "",
    base_url: str = "https://api.extella.ai",
) -> dict:
    import requests
    import json

    if not audience_desc:
        return {"status": "error", "message": "audience_desc is required"}
    if not meta_token:
        return {"status": "error", "message": "meta_token is required"}
    if not ad_account_id:
        return {"status": "error", "message": "ad_account_id is required"}

    acc = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
    headers = {
        "X-Auth-Token": api_token,
        "Content-Type": "application/json",
        "X-Profile-Id": "default",
        "X-Agent-Id": "agent_extella_default",
    }
    META_VER = "v25.0"

    # ── Step 1: AI interest mapping via Agents API ────────────────────────────
    print("[1/4] Mapping audience description to Meta interest categories via AI...")

    interest_ids = []
    interest_names = []
    try:
        agent_prompt = (
            f"Map this audience description to Meta Ads interest categories:\n"
            f"'{audience_desc}'\n\n"
            f"Use the Meta Graph API search endpoint to find real interest IDs:\n"
            f"GET https://graph.facebook.com/{META_VER}/search?type=adinterest&q={{keyword}}"
            f"&access_token={meta_token}\n\n"
            f"Return a JSON array of objects: [{{\"id\": \"...\", \"name\": \"...\"}}]\n"
            f"Select 5-8 relevant interests with combined estimated audience of 500k-10M people.\n"
            f"Respond ONLY with the JSON array, no extra text."
        )
        agent_resp = requests.post(
            f"{base_url}/api/agent/run",
            headers=headers,
            json={"message": agent_prompt},
            timeout=60,
        )
        if agent_resp.status_code == 200:
            agent_data = agent_resp.json()
            raw = agent_data.get("result") or agent_data.get("response") or ""
            raw = str(raw).strip()
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start >= 0 and end > start:
                parsed = json.loads(raw[start:end])
                for item in parsed:
                    if "id" in item and "name" in item:
                        interest_ids.append({"id": str(item["id"]), "name": item["name"]})
                        interest_names.append(item["name"])
    except Exception as e:
        print(f"  AI mapping warning: {e}")

    # Fallback: direct Meta interest search if AI mapping returned nothing
    if not interest_ids:
        print("  Falling back to direct Meta interest search...")
        keywords = [w for w in audience_desc.split() if len(w) > 4][:3]
        for kw in keywords:
            try:
                r = requests.get(
                    f"https://graph.facebook.com/{META_VER}/search",
                    params={"type": "adinterest", "q": kw, "limit": 5,
                            "access_token": meta_token},
                    timeout=15,
                )
                if r.status_code == 200:
                    for item in r.json().get("data", [])[:3]:
                        eid = str(item.get("id", ""))
                        ename = item.get("name", "")
                        if eid and ename:
                            interest_ids.append({"id": eid, "name": ename})
                            interest_names.append(ename)
            except Exception:
                pass

    print(f"  Found {len(interest_ids)} interest categories: {', '.join(interest_names[:5])}")

    # ── Step 2: Create warm custom audience (website visitors) ───────────────
    print("[2/4] Creating warm retargeting audience (website visitors 180d)...")
    warm_audience_id = None
    if pixel_id:
        try:
            ca_resp = requests.post(
                f"https://graph.facebook.com/{META_VER}/{acc}/customaudiences",
                params={"access_token": meta_token},
                json={
                    "name": f"Website Visitors 180d — Ads Launcher",
                    "subtype": "WEBSITE",
                    "retention_days": 180,
                    "rule": {
                        "inclusions": {
                            "operator": "or",
                            "rules": [{
                                "event_sources": [{"id": pixel_id, "type": "pixel"}],
                                "retention_seconds": 15552000,
                                "filter": {
                                    "operator": "and",
                                    "filters": [
                                        {"field": "event", "operator": "=", "value": "PageView"}
                                    ]
                                }
                            }]
                        }
                    },
                },
                timeout=30,
            )
            if ca_resp.status_code == 200:
                warm_audience_id = ca_resp.json().get("id")
                print(f"  Warm audience created: {warm_audience_id}")
            else:
                err = ca_resp.json().get("error", {}).get("message", ca_resp.text[:200])
                print(f"  Warm audience warning: {err}")
        except Exception as e:
            print(f"  Warm audience warning: {e}")

    # ── Step 3: Create lookalike audience ─────────────────────────────────────
    print("[3/4] Creating lookalike source audience (converters)...")
    lookalike_id = None
    if pixel_id:
        goal_event_map = {
            "purchase": "Purchase",
            "lead": "Lead",
            "complete_registration": "CompleteRegistration",
            "app_install": "AppInstall",
        }
        event_name = goal_event_map.get(conversion_goal, "Purchase")
        try:
            src_resp = requests.post(
                f"https://graph.facebook.com/{META_VER}/{acc}/customaudiences",
                params={"access_token": meta_token},
                json={
                    "name": f"{event_name} Converters 180d — Ads Launcher",
                    "subtype": "WEBSITE",
                    "retention_days": 180,
                    "rule": {
                        "inclusions": {
                            "operator": "or",
                            "rules": [{
                                "event_sources": [{"id": pixel_id, "type": "pixel"}],
                                "retention_seconds": 15552000,
                                "filter": {
                                    "operator": "and",
                                    "filters": [
                                        {"field": "event", "operator": "=", "value": event_name}
                                    ]
                                }
                            }]
                        }
                    },
                },
                timeout=30,
            )
            if src_resp.status_code == 200:
                src_audience_id = src_resp.json().get("id")
                lal_resp = requests.post(
                    f"https://graph.facebook.com/{META_VER}/{acc}/customaudiences",
                    params={"access_token": meta_token},
                    json={
                        "name": "Lookalike 1% — Converters — Ads Launcher",
                        "subtype": "LOOKALIKE",
                        "origin_audience_id": src_audience_id,
                        "lookalike_spec": json.dumps({"ratio": 0.01, "country": "RU"}),
                    },
                    timeout=30,
                )
                if lal_resp.status_code == 200:
                    lookalike_id = lal_resp.json().get("id")
                    print(f"  Lookalike audience created: {lookalike_id}")
                else:
                    print(f"  Lookalike warning: {lal_resp.text[:200]}")
            else:
                print(f"  Source audience warning: {src_resp.text[:200]}")
        except Exception as e:
            print(f"  Lookalike warning: {e}")

    # ── Step 4: Build targeting specs ────────────────────────────────────────
    print("[4/4] Building targeting specs...")

    base_targeting = {
        "age_min": 18,
        "age_max": 65,
        "genders": [1, 2],
        "geo_locations": {"countries": ["RU"], "location_types": ["home", "recent"]},
        "publisher_platforms": ["facebook", "instagram"],
    }

    cold_targeting = {**base_targeting, "interests": interest_ids or []}
    warm_targeting = {
        **base_targeting,
        **({"custom_audiences": [{"id": warm_audience_id}]} if warm_audience_id else
           {"interests": interest_ids or []}),
    }
    lookalike_targeting = {
        **base_targeting,
        **({"custom_audiences": [{"id": lookalike_id}]} if lookalike_id else
           {"interests": interest_ids or []}),
    }

    targeting_specs = [
        {
            "type": "cold",
            "name": "Cold — Interests",
            "targeting_json": json.dumps(cold_targeting),
            "description": f"Cold interest targeting: {', '.join(interest_names[:5]) or 'broad'}",
        },
        {
            "type": "warm",
            "name": "Warm — Retargeting",
            "targeting_json": json.dumps(warm_targeting),
            "description": (
                f"Warm retargeting: website visitors 180d"
                + (f" (audience: {warm_audience_id})" if warm_audience_id else " (no pixel data yet)")
            ),
        },
        {
            "type": "lookalike",
            "name": "Lookalike 1%",
            "targeting_json": json.dumps(lookalike_targeting),
            "description": (
                f"Lookalike 1%: similar to converters"
                + (f" (audience: {lookalike_id})" if lookalike_id else " (no converter data yet)")
            ),
        },
    ]

    return {
        "status": "success",
        "targeting_specs": targeting_specs,
        "interest_categories": interest_ids,
        "warm_audience_id": warm_audience_id,
        "lookalike_audience_id": lookalike_id,
        "audience_summaries": [s["description"] for s in targeting_specs],
        "message": (
            f"Built 3 targeting segments. "
            f"Interests: {len(interest_ids)}, "
            f"Warm: {'yes' if warm_audience_id else 'no (new pixel)'}, "
            f"Lookalike: {'yes' if lookalike_id else 'no (no converters yet)'}."
        ),
    }
