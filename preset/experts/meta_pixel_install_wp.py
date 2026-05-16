$extens("include.py")
include("import requests", ["extella-pip install requests"])

def meta_pixel_install_wp(
    wp_url: str = "",
    wp_username: str = "",
    wp_app_password: str = "",
    ftp_host: str = "",
    ftp_user: str = "",
    ftp_pass: str = "",
    pixel_code: str = "",
    pixel_id: str = "",
) -> dict:
    import requests
    import ftplib
    import io
    from requests.auth import HTTPBasicAuth

    print("[1/4] Checking WordPress site and REST API...")

    if not pixel_code:
        return {"status": "error", "message": "pixel_code is required"}
    if not wp_url:
        return {"status": "error", "message": "wp_url is required"}

    wp_url = wp_url.rstrip("/")

    # Verify WP REST API accessible
    try:
        resp = requests.get(f"{wp_url}/wp-json/wp/v2/", timeout=15)
        wp_rest_available = resp.status_code == 200
    except Exception:
        wp_rest_available = False

    active_theme = None
    if wp_rest_available and wp_username and wp_app_password:
        print("[2/4] Getting active theme via WP REST API...")
        try:
            auth = HTTPBasicAuth(wp_username, wp_app_password)
            themes_resp = requests.get(
                f"{wp_url}/wp-json/wp/v2/themes",
                params={"status": "active"},
                auth=auth, timeout=15)
            if themes_resp.status_code == 200:
                themes_data = themes_resp.json()
                if themes_data:
                    active_theme = themes_data[0].get("stylesheet") or themes_data[0].get("template")
        except Exception:
            pass

    print(f"[2/4] Active theme: {active_theme or 'unknown'}")

    # Try FTP installation
    if ftp_host and ftp_user and ftp_pass:
        print("[3/4] Connecting via FTP to inject pixel...")
        try:
            ftp = ftplib.FTP()
            ftp.connect(ftp_host, 21, timeout=30)
            ftp.set_pasv(True)
            ftp.login(ftp_user, ftp_pass)
        except Exception as e:
            return {"status": "error", "message": f"FTP connection failed: {e}"}

        # Build candidate paths for header.php
        candidates = []
        if active_theme:
            candidates = [
                f"/wp-content/themes/{active_theme}/header.php",
                f"/public_html/wp-content/themes/{active_theme}/header.php",
                f"/www/wp-content/themes/{active_theme}/header.php",
                f"/httpdocs/wp-content/themes/{active_theme}/header.php",
            ]

        # If no theme known, scan for themes directory
        if not candidates or not active_theme:
            theme_roots = [
                "/public_html/wp-content/themes/",
                "/wp-content/themes/",
                "/www/wp-content/themes/",
                "/httpdocs/wp-content/themes/",
            ]
            for root in theme_roots:
                try:
                    dirs = ftp.nlst(root)
                    for d in dirs:
                        dir_name = d.split("/")[-1]
                        if dir_name not in (".", "..", "twenty", "twentytwenty",
                                            "twentytwentyone", "twentytwentytwo",
                                            "twentytwentythree", "twentytwentyfour"):
                            candidates.append(f"{root}{dir_name}/header.php")
                    # Also try first available
                    for d in dirs[:3]:
                        dir_name = d.split("/")[-1]
                        if dir_name not in (".", ".."):
                            candidates.append(f"{root}{dir_name}/header.php")
                    break
                except Exception:
                    continue

        target_path = None
        for path in candidates:
            try:
                ftp.size(path)
                target_path = path
                break
            except Exception:
                continue

        if not target_path:
            ftp.quit()
            return {
                "status": "manual_required",
                "install_method": "wp_manual",
                "message": "Could not find header.php via FTP.",
                "instructions": (
                    "1. Connect to your FTP server\n"
                    f"2. Navigate to: wp-content/themes/YOUR_THEME/header.php\n"
                    "3. Open the file and paste the pixel code after <head>\n"
                    "4. Save the file\n"
                    "Alternative: WP Admin → Appearance → Theme Editor → header.php"
                ),
                "pixel_code": pixel_code,
            }

        # Download, inject, upload
        try:
            buf = io.BytesIO()
            ftp.retrbinary(f"RETR {target_path}", buf.write)
            content = buf.getvalue().decode("utf-8", errors="replace")

            if "<!-- Meta Pixel Code" in content or "fbevents.js" in content:
                ftp.quit()
                return {"status": "already_installed", "path": target_path,
                        "install_method": "wp_ftp"}

            # Inject after <head> or before wp_head
            for marker in ("<head>", "<HEAD>", "<?php wp_head(); ?>"):
                if marker in content:
                    new_content = content.replace(
                        marker, marker + "\n" + pixel_code + "\n", 1)
                    break
            else:
                new_content = pixel_code + "\n" + content

            upload_buf = io.BytesIO(new_content.encode("utf-8"))
            ftp.storbinary(f"STOR {target_path}", upload_buf)
            ftp.quit()
        except Exception as e:
            try: ftp.quit()
            except: pass
            return {"status": "error", "message": f"FTP file operation failed: {e}"}

        print(f"[4/4] Pixel injected into {target_path}")

        return {
            "status": "success",
            "install_method": "wp_ftp",
            "theme": active_theme,
            "path": target_path,
            "message": f"Pixel code injected into WordPress theme header.php",
        }

    # No FTP credentials — manual mode
    print("[4/4] No FTP credentials, providing manual instructions...")
    theme_path = f"wp-content/themes/{active_theme}/header.php" if active_theme else "wp-content/themes/YOUR_THEME/header.php"

    return {
        "status": "manual_required",
        "install_method": "wp_manual",
        "theme": active_theme,
        "message": "No FTP credentials provided. Manual installation required.",
        "instructions": (
            f"Option A — Theme Editor:\n"
            f"1. WP Admin → Appearance → Theme Editor\n"
            f"2. Select 'Theme Header (header.php)'\n"
            f"3. Find <head> tag\n"
            f"4. Paste pixel code immediately after <head>\n"
            f"5. Click 'Update File'\n\n"
            f"Option B — Plugin (easier):\n"
            f"1. Install 'Head & Footer Code' plugin (free)\n"
            f"2. Settings → Head & Footer Code\n"
            f"3. Paste pixel code in HEAD section → Save"
        ),
        "pixel_code": pixel_code,
        "file_path": theme_path,
    }
