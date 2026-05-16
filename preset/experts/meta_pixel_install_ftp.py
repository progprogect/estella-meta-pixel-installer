$extens("include.py")

def meta_pixel_install_ftp(
    ftp_host: str = "",
    ftp_user: str = "",
    ftp_pass: str = "",
    ftp_path: str = "",
    pixel_code: str = "",
    pixel_id: str = "",
    ftp_port: int = 21,
) -> dict:
    import ftplib
    import io

    print("[1/4] Validating FTP parameters...")

    if not pixel_code:
        return {"status": "error", "message": "pixel_code is required"}
    if not ftp_host or not ftp_user or not ftp_pass:
        return {
            "status": "manual_required",
            "install_method": "ftp_manual",
            "message": "FTP credentials not provided. Manual installation required.",
            "pixel_code": pixel_code,
        }

    print(f"[2/4] Connecting to FTP {ftp_host}:{ftp_port}...")

    try:
        ftp = ftplib.FTP()
        ftp.connect(ftp_host, ftp_port, timeout=30)
        ftp.set_pasv(True)
        ftp.login(ftp_user, ftp_pass)
    except Exception as e:
        return {"status": "error", "message": f"FTP connection failed: {e}"}

    print("[3/4] Finding main HTML file...")

    # Determine target file
    if ftp_path:
        target_path = ftp_path
    else:
        # Auto-detect main HTML/PHP file
        candidates = [
            "/public_html/index.html",
            "/public_html/index.php",
            "/www/index.html",
            "/www/index.php",
            "/httpdocs/index.html",
            "/httpdocs/index.php",
            "/index.html",
            "/index.php",
            "/public/index.html",
        ]
        target_path = None
        for path in candidates:
            try:
                ftp.size(path)
                target_path = path
                break
            except Exception:
                continue

        if not target_path:
            # Try listing root to find the web root
            try:
                root_dirs = ftp.nlst("/")
                for dir_name in ["public_html", "www", "httpdocs", "html", "web"]:
                    if dir_name in root_dirs:
                        for fname in ["index.html", "index.php"]:
                            candidate = f"/{dir_name}/{fname}"
                            try:
                                ftp.size(candidate)
                                target_path = candidate
                                break
                            except: pass
                        if target_path:
                            break
            except: pass

    if not target_path:
        ftp.quit()
        return {
            "status": "error",
            "message": "Could not find HTML file via FTP. Please provide ftp_path parameter with the path to your main HTML file.",
            "pixel_code": pixel_code,
        }

    print(f"[3/4] Target file: {target_path}")

    # Download, inject, upload
    try:
        buf = io.BytesIO()
        ftp.retrbinary(f"RETR {target_path}", buf.write)
        content = buf.getvalue().decode("utf-8", errors="replace")
    except Exception as e:
        ftp.quit()
        return {"status": "error", "message": f"Could not download file {target_path}: {e}"}

    # Check if already installed
    if "<!-- Meta Pixel Code" in content or "fbevents.js" in content:
        ftp.quit()
        return {
            "status": "already_installed",
            "install_method": "ftp",
            "path": target_path,
            "message": "Meta Pixel code already detected in the file",
        }

    # Inject pixel code
    new_content = None
    for marker in ("<head>", "<HEAD>", "</title>", "<body>", "<BODY>"):
        if marker in content:
            new_content = content.replace(marker, marker + "\n" + pixel_code + "\n", 1)
            break

    if new_content is None:
        # Fallback: inject before </body>
        if "</body>" in content.lower():
            pos = content.lower().rfind("</body>")
            new_content = content[:pos] + pixel_code + "\n" + content[pos:]
        else:
            new_content = pixel_code + "\n" + content

    print(f"[4/4] Uploading modified file...")

    try:
        upload_buf = io.BytesIO(new_content.encode("utf-8"))
        ftp.storbinary(f"STOR {target_path}", upload_buf)
        ftp.quit()
    except Exception as e:
        try: ftp.quit()
        except: pass
        return {"status": "error", "message": f"Could not upload modified file: {e}"}

    return {
        "status": "success",
        "install_method": "ftp",
        "path": target_path,
        "ftp_host": ftp_host,
        "message": f"Pixel code injected into {target_path}",
    }
