$extens("include.py")
include("import requests", ["extella-pip install requests"])

def ads_creative_upload(
    creatives_json: str = "",
    ad_copy: str = "",
    headline: str = "",
    link_url: str = "",
    call_to_action: str = "LEARN_MORE",
    page_id: str = "",
    ad_account_id: str = "",
    meta_token: str = "",
    api_token: str = "",
    base_url: str = "https://api.extella.ai",
) -> dict:
    import requests
    import json
    import base64

    if not meta_token:
        return {"status": "error", "message": "meta_token is required"}
    if not ad_account_id:
        return {"status": "error", "message": "ad_account_id is required"}
    if not page_id:
        return {"status": "error", "message": "page_id is required (Facebook Page ID)"}
    if not link_url:
        return {"status": "error", "message": "link_url is required (destination URL)"}

    acc = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
    META_VER = "v25.0"

    VALID_CTAS = {
        "LEARN_MORE", "SHOP_NOW", "SIGN_UP", "DOWNLOAD", "GET_OFFER",
        "BOOK_TRAVEL", "CONTACT_US", "APPLY_NOW", "SUBSCRIBE",
    }
    cta = call_to_action.upper()
    if cta not in VALID_CTAS:
        cta = "LEARN_MORE"

    # ── Parse creatives list ──────────────────────────────────────────────────
    creatives_list = []
    if creatives_json:
        try:
            parsed = json.loads(creatives_json)
            if isinstance(parsed, list):
                creatives_list = parsed
            elif isinstance(parsed, str):
                creatives_list = [parsed]
        except (json.JSONDecodeError, TypeError):
            creatives_list = [s.strip() for s in creatives_json.split(",") if s.strip()]

    if not creatives_list:
        return {"status": "error", "message": "creatives_json must contain at least one image URL or base64 string"}

    creative_ids = []
    image_hashes = []
    preview_urls = []
    errors = []

    for idx, creative_src in enumerate(creatives_list):
        print(f"[{idx+1}/{len(creatives_list)}] Processing creative...")

        # ── Upload image ──────────────────────────────────────────────────────
        image_hash = None
        try:
            if creative_src.startswith("http://") or creative_src.startswith("https://"):
                img_resp = requests.get(creative_src, timeout=30)
                if img_resp.status_code != 200:
                    errors.append(f"Creative {idx+1}: failed to download image from URL")
                    continue
                img_bytes = img_resp.content
                img_b64 = base64.b64encode(img_bytes).decode()
            elif creative_src.startswith("data:image"):
                img_b64 = creative_src.split(",", 1)[1]
            else:
                img_b64 = creative_src

            upload_resp = requests.post(
                f"https://graph.facebook.com/{META_VER}/{acc}/adimages",
                params={"access_token": meta_token},
                json={"bytes": img_b64},
                timeout=60,
            )
            if upload_resp.status_code != 200:
                err = upload_resp.json().get("error", {}).get("message", upload_resp.text[:300])
                errors.append(f"Creative {idx+1}: image upload failed — {err}")
                continue

            images_data = upload_resp.json().get("images", {})
            for fname, img_info in images_data.items():
                image_hash = img_info.get("hash")
                break

            if not image_hash:
                errors.append(f"Creative {idx+1}: no image hash in upload response")
                continue

            print(f"  Image hash: {image_hash}")
            image_hashes.append(image_hash)

        except Exception as e:
            errors.append(f"Creative {idx+1}: image processing error — {str(e)}")
            continue

        # ── Create ad creative ────────────────────────────────────────────────
        try:
            creative_name = f"Creative {idx+1} — Ads Launcher"
            creative_payload = {
                "name": creative_name,
                "object_story_spec": {
                    "page_id": page_id,
                    "link_data": {
                        "message": ad_copy or f"Check out our offer at {link_url}",
                        "link": link_url,
                        "image_hash": image_hash,
                        "name": headline or "Learn More",
                        "call_to_action": {
                            "type": cta,
                            "value": {"link": link_url},
                        },
                    },
                },
            }

            cr_resp = requests.post(
                f"https://graph.facebook.com/{META_VER}/{acc}/adcreatives",
                params={"access_token": meta_token},
                json=creative_payload,
                timeout=30,
            )
            if cr_resp.status_code != 200:
                err = cr_resp.json().get("error", {}).get("message", cr_resp.text[:300])
                errors.append(f"Creative {idx+1}: adcreative creation failed — {err}")
                continue

            creative_id = cr_resp.json().get("id")
            creative_ids.append(creative_id)
            print(f"  Creative ID: {creative_id}")

            # Generate preview URL
            preview_url = (
                f"https://www.facebook.com/ads/creativehub/preview/?creative_id={creative_id}"
                f"&access_token={meta_token}"
            )
            preview_urls.append(preview_url)

        except Exception as e:
            errors.append(f"Creative {idx+1}: creative creation error — {str(e)}")
            continue

    if not creative_ids:
        return {
            "status": "error",
            "message": "No creatives were successfully created",
            "errors": errors,
        }

    return {
        "status": "success",
        "creative_ids": creative_ids,
        "image_hashes": image_hashes,
        "creative_previews": preview_urls,
        "errors": errors,
        "message": (
            f"Created {len(creative_ids)} ad creative(s) successfully."
            + (f" {len(errors)} error(s)." if errors else "")
        ),
    }
