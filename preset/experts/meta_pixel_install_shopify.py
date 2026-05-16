$extens("include.py")
include("import requests", ["extella-pip install requests"])

def meta_pixel_install_shopify(
    shop_domain: str = "",
    shopify_access_token: str = "",
    pixel_code: str = "",
    pixel_id: str = "",
) -> dict:
    import requests

    print("[1/4] Validating Shopify credentials...")

    if not pixel_code:
        return {"status": "error", "message": "pixel_code is required"}
    if not shop_domain or not shopify_access_token:
        return {
            "status": "manual_required",
            "install_method": "shopify_manual",
            "message": "Shopify credentials not provided.",
            "instructions": (
                "1. Shopify Admin → Online Store → Themes\n"
                "2. Click '...' → Edit code\n"
                "3. Open Layout → theme.liquid\n"
                "4. Find <head> tag\n"
                "5. Paste pixel code immediately after <head>\n"
                "6. Save"
            ),
            "pixel_code": pixel_code,
        }

    # Normalize domain
    shop_domain = shop_domain.replace("https://", "").replace("http://", "").rstrip("/")

    auth_headers = {
        "X-Shopify-Access-Token": shopify_access_token,
        "Content-Type": "application/json",
    }
    api_base = f"https://{shop_domain}/admin/api/2024-01"

    print("[2/4] Verifying Shopify connection and getting active theme...")

    # Verify connection + get shop info
    try:
        shop_resp = requests.get(f"{api_base}/shop.json", headers=auth_headers, timeout=15)
        shop_resp.raise_for_status()
        shop_name = shop_resp.json()["shop"]["name"]
    except Exception as e:
        return {"status": "error", "message": f"Shopify connection failed: {e}. Check shop_domain and access_token."}

    # Get active theme
    try:
        themes_resp = requests.get(f"{api_base}/themes.json", headers=auth_headers, timeout=15)
        themes = themes_resp.json().get("themes", [])
        active_theme = next((t for t in themes if t.get("role") == "main"), None)
        if not active_theme:
            active_theme = themes[0] if themes else None
        if not active_theme:
            return {"status": "error", "message": "No active theme found in Shopify store"}
        theme_id = active_theme["id"]
        theme_name = active_theme.get("name", "")
    except Exception as e:
        return {"status": "error", "message": f"Could not get Shopify themes: {e}"}

    print(f"[3/4] Reading theme.liquid for theme '{theme_name}' (ID: {theme_id})...")

    # Get theme.liquid content
    try:
        asset_resp = requests.get(
            f"{api_base}/themes/{theme_id}/assets.json",
            params={"asset[key]": "layout/theme.liquid"},
            headers=auth_headers, timeout=30)
        asset_resp.raise_for_status()
        theme_liquid = asset_resp.json()["asset"]["value"]
    except Exception as e:
        return {"status": "error", "message": f"Could not read theme.liquid: {e}"}

    # Check if already installed
    if "<!-- Meta Pixel Code" in theme_liquid or "fbevents.js" in theme_liquid:
        return {
            "status": "already_installed",
            "install_method": "shopify_api",
            "theme": theme_name,
            "message": "Meta Pixel code already detected in theme.liquid",
        }

    # Inject after <head>
    if "<head>" in theme_liquid:
        new_content = theme_liquid.replace("<head>", "<head>\n" + pixel_code + "\n", 1)
    else:
        new_content = pixel_code + "\n" + theme_liquid

    print(f"[4/4] Updating theme.liquid...")

    # Update theme.liquid
    try:
        update_resp = requests.put(
            f"{api_base}/themes/{theme_id}/assets.json",
            headers=auth_headers,
            json={"asset": {"key": "layout/theme.liquid", "value": new_content}},
            timeout=30)
        update_resp.raise_for_status()
    except Exception as e:
        return {"status": "error", "message": f"Could not update theme.liquid: {e}"}

    return {
        "status": "success",
        "install_method": "shopify_api",
        "shop_name": shop_name,
        "shop_domain": shop_domain,
        "theme_name": theme_name,
        "theme_id": theme_id,
        "message": f"Pixel code injected into theme.liquid for Shopify store '{shop_name}'",
    }
