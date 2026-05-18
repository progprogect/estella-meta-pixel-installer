$extens("include.py")
include("import pycookiecheat", ["extella-pip install pycookiecheat"])
include("import playwright", ["extella-pip install playwright"])

def meta_pixel_create_headless(
    pixel_name: str = "",
    landing_url: str = "",
    api_token: str = "",
    base_url: str = "https://api.extella.ai",
    headless: bool = True,
) -> dict:
    import re
    import time
    from urllib.parse import urlparse

    # ─── Auto-generate pixel name ────────────────────────────────────────────

    if not pixel_name and landing_url:
        try:
            domain = urlparse(landing_url).netloc.replace("www.", "")
            pixel_name = f"Pixel — {domain}"
        except Exception:
            pixel_name = "Meta Pixel (Extella)"
    elif not pixel_name:
        pixel_name = "Meta Pixel (Extella)"

    # ─── 1. Check Playwright ─────────────────────────────────────────────────

    print("[1/5] Checking Playwright...")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "status": "setup_required",
            "message": "Playwright is not installed. Run expert `meta_playwright_setup` first.",
            "action": "run meta_playwright_setup",
        }

    # ─── 2. Extract Facebook session cookies ─────────────────────────────────

    print("[2/5] Extracting Facebook session from browser...")

    fb_cookies = {}
    browser_used = None

    try:
        from pycookiecheat import chrome_cookies
        fb_cookies = chrome_cookies("https://www.facebook.com")
        if fb_cookies.get("c_user"):
            browser_used = "chrome"
            print(f"  Chrome session found (user_id: {fb_cookies.get('c_user', '?')})")
    except Exception as chrome_err:
        print(f"  Chrome: {chrome_err}")

    if not fb_cookies.get("c_user"):
        try:
            from pycookiecheat import firefox_cookies
            fb_cookies = firefox_cookies("https://www.facebook.com")
            if fb_cookies.get("c_user"):
                browser_used = "firefox"
                print(f"  Firefox session found (user_id: {fb_cookies.get('c_user', '?')})")
        except Exception as ff_err:
            print(f"  Firefox: {ff_err}")

    if not fb_cookies.get("c_user"):
        return {
            "status": "not_logged_in",
            "message": (
                "No active Facebook session found in your browser. "
                "Please open https://www.facebook.com, log in, and then retry."
            ),
        }

    # ─── 3. Build Playwright cookie list ─────────────────────────────────────

    print(f"[3/5] Injecting {len(fb_cookies)} cookies into headless browser...")

    playwright_cookies = []
    for name, value in fb_cookies.items():
        for domain in (".facebook.com", ".business.facebook.com"):
            playwright_cookies.append({
                "name": name,
                "value": str(value),
                "domain": domain,
                "path": "/",
                "httpOnly": False,
                "secure": True,
                "sameSite": "None",
            })

    # ─── 4. Browser automation ───────────────────────────────────────────────

    print(f"[4/5] Opening Events Manager (headless={headless})...")

    pixel_id = None
    error_detail = None

    try:
        with sync_playwright() as p:
            # Try system Chrome first (faster, no 150 MB download), then bundled Chromium
            browser_obj = None
            for launch_kwargs in [
                {"channel": "chrome", "headless": headless,
                 "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"]},
                {"headless": headless,
                 "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox",
                          "--disable-dev-shm-usage"]},
            ]:
                try:
                    browser_obj = p.chromium.launch(**launch_kwargs)
                    print(f"  Browser launched (channel={launch_kwargs.get('channel', 'chromium')})")
                    break
                except Exception:
                    continue

            if not browser_obj:
                return {
                    "status": "setup_required",
                    "message": "Could not launch browser. Run expert `meta_playwright_setup` to install Chromium.",
                    "action": "run meta_playwright_setup",
                }

            ctx = browser_obj.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
            )
            ctx.add_cookies(playwright_cookies)
            page = ctx.new_page()

            # ── Navigate to Events Manager ────────────────────────────────────

            try:
                page.goto("https://business.facebook.com/events_manager2/list/", timeout=45000)
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass  # Work with whatever loaded

            current_url = page.url
            print(f"  Page URL: {current_url}")

            if any(x in current_url for x in ("login", "checkpoint", "recover")):
                browser_obj.close()
                return {
                    "status": "session_expired",
                    "message": (
                        "Facebook session expired or rejected. "
                        "Please log in to Facebook in your browser and retry."
                    ),
                }

            # ── Step A: Click "Connect Data Sources" or equivalent ────────────

            print("[5/5] Automating pixel creation UI...")

            def try_click(selectors, timeout_ms=5000):
                for sel in selectors:
                    try:
                        page.click(sel, timeout=timeout_ms)
                        print(f"  Clicked: {sel!r}")
                        return True
                    except Exception:
                        continue
                return False

            def try_fill(selectors, value, timeout_ms=5000):
                for sel in selectors:
                    try:
                        el = page.locator(sel).first
                        if el.count() > 0:
                            el.clear()
                            el.fill(value)
                            print(f"  Filled '{value}' in: {sel!r}")
                            return True
                    except Exception:
                        continue
                return False

            # Click "Connect Data Sources" / "+ Add" / "New Dataset"
            create_btn_found = try_click([
                'button:has-text("Connect Data Sources")',
                'text="Connect Data Sources"',
                '[aria-label="Connect Data Sources"]',
                'button:has-text("Add New Data Source")',
                'a:has-text("Connect Data Sources")',
            ])

            if not create_btn_found:
                # Try direct creation URL as fallback
                print("  Create button not found, trying direct URL...")
                try:
                    page.goto(
                        "https://business.facebook.com/events_manager2/list/dataset/create/",
                        timeout=30000,
                    )
                    page.wait_for_load_state("networkidle", timeout=20000)
                except Exception:
                    pass

            time.sleep(2)

            # ── Step B: Select "Web" data source type ─────────────────────────

            try_click([
                'div[role="radio"]:has-text("Web")',
                'label:has-text("Web")',
                'text="Web"',
                '[aria-label="Web"]',
                'button:has-text("Web")',
            ], timeout_ms=6000)

            time.sleep(1)

            # ── Step C: Select "Facebook Pixel" vs API ────────────────────────

            try_click([
                'div[role="radio"]:has-text("Facebook Pixel")',
                'label:has-text("Facebook Pixel")',
                'text="Facebook Pixel"',
                'div[role="radio"]:has-text("Meta Pixel")',
                'label:has-text("Meta Pixel")',
                'text="Meta Pixel"',
            ], timeout_ms=5000)

            time.sleep(1)

            # ── Step D: Click Next / Connect if shown ─────────────────────────

            try_click([
                'button:has-text("Next")',
                'button:has-text("Connect")',
                'button:has-text("Continue")',
                'text="Next"',
            ], timeout_ms=3000)

            time.sleep(1)

            # ── Step E: Fill pixel name ───────────────────────────────────────

            try_fill([
                'input[placeholder*="ame"]',
                'input[placeholder*="pixel"]',
                'input[aria-label*="name"]',
                'input[aria-label*="Name"]',
                'input[name="name"]',
                'input[type="text"]',
            ], pixel_name)

            time.sleep(1)

            # ── Step F: Click "Create" ────────────────────────────────────────

            try_click([
                'button:has-text("Create")',
                'button[type="submit"]:has-text("Create")',
                'text="Create Pixel"',
                'text="Create pixel"',
                'button[type="submit"]',
            ], timeout_ms=6000)

            # ── Step G: Wait for pixel ID in URL ─────────────────────────────

            print("  Waiting for redirect to pixel detail page...")
            try:
                page.wait_for_url(re.compile(r"/pixel/\d+"), timeout=20000)
            except Exception:
                pass

            time.sleep(3)

            final_url = page.url
            print(f"  Final URL: {final_url}")

            # ── Step H: Extract pixel ID ──────────────────────────────────────

            for pattern in (
                r"/pixel/(\d{10,})",
                r"/dataset/(\d{10,})",
                r"pixel_id=(\d{10,})",
                r"/(\d{15,})/overview",
            ):
                m = re.search(pattern, final_url)
                if m:
                    pixel_id = m.group(1)
                    print(f"  Pixel ID from URL: {pixel_id}")
                    break

            if not pixel_id:
                # Try page content as last resort
                try:
                    content = page.content()
                    for pat in (
                        r'"pixelId"\s*:\s*"(\d{10,})"',
                        r'"pixel_id"\s*:\s*"(\d{10,})"',
                        r'"id"\s*:\s*"(\d{15,})"',
                        r'data-pixel-id="(\d{10,})"',
                    ):
                        m = re.search(pat, content)
                        if m:
                            pixel_id = m.group(1)
                            print(f"  Pixel ID from page content: {pixel_id}")
                            break
                except Exception:
                    pass

            browser_obj.close()

    except Exception as outer_err:
        error_detail = str(outer_err)
        print(f"  Browser automation error: {error_detail}")

    # ─── 5. Build result ─────────────────────────────────────────────────────

    if not pixel_id:
        return {
            "status": "error",
            "message": (
                "Could not automatically create the pixel via browser automation. "
                "Events Manager UI may have changed or session was rejected."
            ),
            "details": error_detail or "No pixel ID found in URL or page content.",
            "fallback": (
                "Option A: Run meta_playwright_setup to verify Chromium is working, then retry. "
                "Option B: Run meta_app_onboarding_assistant to set up OAuth credentials and "
                "use the standard meta_token_from_browser flow."
            ),
        }

    # Build standard pixel code snippet
    pixel_code = (
        "<!-- Meta Pixel Code -->\n"
        "<script>\n"
        "!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?\n"
        "n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;\n"
        "n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;\n"
        "t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,\n"
        "document,'script','https://connect.facebook.net/en_US/fbevents.js');\n"
        f"fbq('init', '{pixel_id}');\n"
        "fbq('track', 'PageView');\n"
        "</script>\n"
        "<noscript><img height=\"1\" width=\"1\" style=\"display:none\"\n"
        f"src=\"https://www.facebook.com/tr?id={pixel_id}&ev=PageView&noscript=1\"/></noscript>\n"
        "<!-- End Meta Pixel Code -->"
    )

    lead_snippet = (
        "\n<script>\n"
        "/* Meta Pixel — Auto Lead tracking on form submit (by Extella) */\n"
        "document.addEventListener('DOMContentLoaded', function() {\n"
        "  document.querySelectorAll('form').forEach(function(f) {\n"
        "    f.addEventListener('submit', function() { fbq('track', 'Lead'); });\n"
        "  });\n"
        "});\n"
        "</script>"
    )

    return {
        "status": "success",
        "pixel_id": pixel_id,
        "pixel_name": pixel_name,
        "pixel_code": pixel_code + lead_snippet,
        "pixel_code_base": pixel_code,
        "events_manager_url": (
            f"https://business.facebook.com/events_manager2/list/pixel/{pixel_id}"
        ),
        "method": "headless_browser",
        "browser_used": browser_used,
    }
