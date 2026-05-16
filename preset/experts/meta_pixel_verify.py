$extens("include.py")
include("import requests", ["extella-pip install requests"])

def meta_pixel_verify(
    pixel_id: str = "",
    meta_access_token: str = "",
    landing_url: str = "",
    wait_seconds: int = 60,
) -> dict:
    import requests
    import time
    from datetime import datetime, timezone

    print("[1/3] Sending test event via Conversions API...")

    if not pixel_id or not meta_access_token:
        return {"status": "error", "message": "pixel_id and meta_access_token are required"}

    BASE = "https://graph.facebook.com/v25.0"

    # Send CAPI test PageView event
    try:
        test_resp = requests.post(
            f"{BASE}/{pixel_id}/events",
            params={"access_token": meta_access_token},
            json={
                "data": [{
                    "event_name": "PageView",
                    "event_time": int(time.time()),
                    "action_source": "website",
                    "event_source_url": landing_url or "https://example.com",
                    "user_data": {
                        "client_ip_address": "1.2.3.4",
                        "client_user_agent": "Mozilla/5.0 (Extella Pixel Installer/1.0)",
                    },
                }],
                "test_event_code": "TEST_EXTELLA_VERIFY",
            },
            timeout=30,
        )
        test_data = test_resp.json()
        events_received = test_data.get("events_received", 0)
        if "error" in test_data:
            print(f"[1/3] CAPI warning: {test_data['error'].get('message', '')}")
    except Exception as e:
        events_received = 0
        print(f"[1/3] CAPI test event failed (non-fatal): {e}")

    print(f"[1/3] Test event sent. Events received: {events_received}")

    # Wait before polling
    print(f"[2/3] Waiting {min(wait_seconds, 30)}s for pixel to register...")
    time.sleep(min(wait_seconds, 30))

    # Poll last_fired_time
    print("[3/3] Checking pixel status in Events Manager...")

    pixel_status = "pending"
    last_fired_time = ""
    is_unavailable = False
    check_interval = 10

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        try:
            resp = requests.get(
                f"{BASE}/{pixel_id}",
                params={
                    "fields": "id,name,last_fired_time,is_unavailable",
                    "access_token": meta_access_token,
                },
                timeout=15,
            )
            data = resp.json()

            if "error" in data:
                pixel_status = "error"
                break

            is_unavailable = data.get("is_unavailable", False)
            if is_unavailable:
                pixel_status = "unavailable"
                break

            last_fired_time = data.get("last_fired_time", "")
            if last_fired_time:
                try:
                    fired_dt = datetime.fromisoformat(last_fired_time.replace("+0000", "+00:00"))
                    seconds_ago = (datetime.now(timezone.utc) - fired_dt).total_seconds()
                    if seconds_ago < 600:
                        pixel_status = "active"
                        break
                except Exception:
                    pass

        except Exception:
            pass

        time.sleep(check_interval)

    status_messages = {
        "active": "Pixel is active and receiving events",
        "pending": "Pixel created successfully. Visit your site to trigger the first browser event.",
        "unavailable": "Pixel is marked unavailable. Check your Meta Business account.",
        "error": "Could not verify pixel status. Check Events Manager manually.",
    }

    return {
        "status": "success",
        "pixel_id": pixel_id,
        "pixel_status": pixel_status,
        "capi_test_events_received": events_received,
        "last_fired_time": last_fired_time,
        "message": status_messages.get(pixel_status, ""),
        "events_manager_url": f"https://business.facebook.com/events_manager2/list/pixel/{pixel_id}",
        "test_events_url": f"https://business.facebook.com/events_manager2/list/pixel/{pixel_id}/test_events",
    }
