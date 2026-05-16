$extens("include.py")
include("import requests", ["extella-pip install requests"])

def meta_site_detector(
    url: str = "",
    timeout: int = 15,
) -> dict:
    import requests
    import re
    from urllib.parse import urlparse

    print("[1/2] Fetching site to detect platform...")

    if not url:
        return {"status": "error", "message": "url is required"}

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ExtellaBot/1.0; +https://extella.ai)"})
    except requests.exceptions.SSLError:
        try:
            resp = requests.get(url.replace("https://", "http://"), timeout=timeout,
                allow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; ExtellaBot/1.0)"})
        except Exception as e:
            return {"status": "error", "message": f"Could not fetch URL: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Could not fetch URL: {e}"}

    headers_lower = {k.lower(): v.lower() for k, v in resp.headers.items()}
    html = resp.text.lower()
    signals = []
    scores = {}

    print("[2/2] Analyzing platform signals...")

    def add(cms, score, signal):
        scores[cms] = scores.get(cms, 0) + score
        signals.append(signal)

    # WordPress
    if "/wp-content/" in html or "/wp-includes/" in html:
        add("wordpress", 0.7, "wp-content in HTML")
    if "wordpress" in html and ("wp-" in html or "wordpress" in headers_lower.get("x-powered-by", "")):
        add("wordpress", 0.2, "wordpress keyword")
    if "api.w.org" in str(headers_lower):
        add("wordpress", 0.5, "WP API link header")
    if "wp-json" in html:
        add("wordpress", 0.3, "wp-json in HTML")

    # Shopify
    if "cdn.shopify.com" in html or "shopify.theme" in html:
        add("shopify", 0.8, "Shopify CDN in HTML")
    if "powered-by" in headers_lower and "shopify" in headers_lower.get("powered-by", ""):
        add("shopify", 0.9, "X-Powered-By: Shopify header")
    if ".myshopify.com" in url.lower():
        add("shopify", 0.9, "myshopify.com domain")

    # Wix
    if "static.wixstatic.com" in html or "parastorage.com" in html:
        add("wix", 0.9, "Wix static CDN")
    if "wix.com" in html or "_wix_" in html:
        add("wix", 0.3, "Wix reference in HTML")

    # Tilda
    if "tildacdn.com" in html or "tilda.cc/zero" in html:
        add("tilda", 0.9, "Tilda CDN")
    if "tilda.cc" in html:
        add("tilda", 0.3, "Tilda reference")

    # Bitrix
    if "/bitrix/" in html:
        add("bitrix", 0.8, "Bitrix path in HTML")
    if "bx.ready" in html or "bitrixvm" in headers_lower.get("server", ""):
        add("bitrix", 0.4, "Bitrix JS signature")

    # Detect GTM (additional signal, not CMS)
    has_gtm = bool(re.search(r"gtm-[a-z0-9]+", resp.text, re.IGNORECASE))
    gtm_id = None
    gtm_match = re.search(r"(GTM-[A-Z0-9]+)", resp.text, re.IGNORECASE)
    if gtm_match:
        gtm_id = gtm_match.group(1).upper()
        signals.append(f"GTM container: {gtm_id}")

    # Check if pixel already installed
    pixel_already_installed = "fbevents.js" in html or "connect.facebook.net" in html
    if pixel_already_installed:
        existing_pixel = re.search(r"fbq\('init',\s*'(\d+)'", resp.text)
        existing_pixel_id = existing_pixel.group(1) if existing_pixel else "unknown"
        signals.append(f"Existing pixel detected: {existing_pixel_id}")

    if not scores:
        cms_type = "unknown"
        confidence = 0.0
    else:
        cms_type = max(scores, key=scores.get)
        confidence = round(min(scores[cms_type], 1.0), 2)

    final_url = resp.url
    domain = urlparse(final_url).netloc

    return {
        "status": "success",
        "url": final_url,
        "domain": domain,
        "cms_type": cms_type,
        "confidence": confidence,
        "has_gtm": has_gtm,
        "gtm_id": gtm_id,
        "pixel_already_installed": pixel_already_installed,
        "signals": signals,
        "http_status": resp.status_code,
    }
