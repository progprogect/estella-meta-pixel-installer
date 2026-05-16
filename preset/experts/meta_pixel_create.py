$extens("include.py")
include("import requests", ["extella-pip install requests"])

def meta_pixel_create(
    meta_access_token: str = "",
    ad_account_id: str = "",
    pixel_name: str = "",
    landing_url: str = "",
) -> dict:
    import requests
    from urllib.parse import urlparse

    print("[1/3] Validating inputs...")

    if not meta_access_token:
        return {"status": "error", "message": "meta_access_token is required"}
    if not ad_account_id:
        return {"status": "error", "message": "ad_account_id is required"}

    # Normalize ad_account_id
    if not ad_account_id.startswith("act_"):
        ad_account_id = f"act_{ad_account_id}"

    # Auto-generate pixel name from domain if not provided
    if not pixel_name and landing_url:
        try:
            domain = urlparse(landing_url).netloc.replace("www.", "")
            pixel_name = f"Pixel — {domain}"
        except Exception:
            pixel_name = "Meta Pixel (Extella)"
    elif not pixel_name:
        pixel_name = "Meta Pixel (Extella)"

    BASE = "https://graph.facebook.com/v25.0"
    auth_params = {"access_token": meta_access_token}

    print(f"[2/3] Creating pixel '{pixel_name}' in account {ad_account_id}...")

    # Create pixel
    try:
        r = requests.post(
            f"{BASE}/{ad_account_id}/adspixels",
            params=auth_params,
            json={"name": pixel_name},
            timeout=30,
        )
        data = r.json()
        if "error" in data:
            err = data["error"]
            return {
                "status": "error",
                "message": f"Meta API error {err.get('code')}: {err.get('message')}",
                "error_code": err.get("code"),
            }
        pixel_id = data.get("id")
        if not pixel_id:
            return {"status": "error", "message": f"Unexpected response: {data}"}
    except Exception as e:
        return {"status": "error", "message": f"Pixel creation failed: {e}"}

    print(f"[3/3] Fetching pixel code for Pixel ID {pixel_id}...")

    # Get pixel code from Meta API
    try:
        r2 = requests.get(
            f"{BASE}/{pixel_id}",
            params={**auth_params, "fields": "id,name,code,creation_time"},
            timeout=30,
        )
        info = r2.json()
        pixel_code = info.get("code", "")
    except Exception:
        pixel_code = ""

    # Fallback: build pixel code manually if API didn't return it
    if not pixel_code:
        pixel_code = f"""<!-- Meta Pixel Code -->
<script>
!function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;
n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}(window,
document,'script','https://connect.facebook.net/en_US/fbevents.js');
fbq('init', '{pixel_id}');
fbq('track', 'PageView');
</script>
<noscript><img height="1" width="1" style="display:none"
src="https://www.facebook.com/tr?id={pixel_id}&ev=PageView&noscript=1"/></noscript>
<!-- End Meta Pixel Code -->"""

    # Append auto-lead tracking snippet
    lead_snippet = """
<script>
/* Meta Pixel — Auto Lead tracking on form submit (by Extella) */
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('form').forEach(function(f) {
    f.addEventListener('submit', function() { fbq('track', 'Lead'); });
  });
});
</script>"""

    pixel_code_with_events = pixel_code + "\n" + lead_snippet

    print(f"[3/3] Done! Pixel ID: {pixel_id}")

    return {
        "status": "success",
        "pixel_id": pixel_id,
        "pixel_name": pixel_name,
        "ad_account_id": ad_account_id,
        "pixel_code": pixel_code_with_events,
        "pixel_code_base": pixel_code,
        "events_manager_url": f"https://business.facebook.com/events_manager2/list/pixel/{pixel_id}",
    }
