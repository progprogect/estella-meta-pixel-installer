$extens("include.py")
include("import playwright", ["extella-pip install playwright"])

def meta_playwright_setup(
    api_token: str = "",
    base_url: str = "https://api.extella.ai",
) -> dict:
    import subprocess
    import sys

    print("[1/3] Verifying Playwright Python package...")

    try:
        import playwright
        pkg_version = getattr(playwright, "__version__", "unknown")
        print(f"  Playwright package: {pkg_version}")
    except ImportError:
        return {
            "status": "error",
            "message": "Playwright package could not be imported after installation attempt.",
            "suggestion": "Run: pip install playwright",
        }

    print("[2/3] Checking Chromium browser binary...")

    chromium_ok = False
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        chromium_ok = True
        print("  Chromium binary: available")
    except Exception as e:
        err = str(e).lower()
        need_install = any(x in err for x in ["executable", "not found", "install", "run playwright install"])
        if need_install:
            print("  Chromium binary not found. Downloading (~150 MB, one-time)...")
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    capture_output=True, text=True, timeout=600,
                )
                if result.returncode == 0:
                    chromium_ok = True
                    print("  Chromium installed successfully")
                else:
                    stderr_snippet = (result.stderr or "")[:600]
                    return {
                        "status": "error",
                        "message": f"Chromium download failed (exit {result.returncode}): {stderr_snippet}",
                        "suggestion": "Run manually: python -m playwright install chromium",
                    }
            except subprocess.TimeoutExpired:
                return {
                    "status": "error",
                    "message": "Chromium download timed out (600 s). Check internet connection and retry.",
                    "suggestion": "Run manually: python -m playwright install chromium",
                }
            except Exception as install_err:
                return {
                    "status": "error",
                    "message": f"Chromium installation command failed: {install_err}",
                    "suggestion": "Run manually: python -m playwright install chromium",
                }
        else:
            return {
                "status": "error",
                "message": f"Unexpected Playwright error: {e}",
            }

    print("[3/3] Running end-to-end launch test...")

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            ctx = browser.new_context(viewport={"width": 1280, "height": 800})
            page = ctx.new_page()
            page.goto("about:blank")
            title = page.title()
            browser.close()
        print("  Launch test passed")
    except Exception as e:
        return {
            "status": "error",
            "message": f"Playwright end-to-end test failed: {e}",
        }

    return {
        "status": "ready",
        "playwright_installed": True,
        "chromium_installed": True,
        "message": "Playwright and Chromium are ready for headless browser automation.",
    }
