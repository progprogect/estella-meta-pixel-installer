$extens("include.py")
include("import requests", ["extella-pip install requests"])

def ads_capi_git_install(
    repo_url: str = "",
    pixel_id: str = "",
    capi_token: str = "",
    github_token: str = "",
    api_token: str = "",
    base_url: str = "https://api.extella.ai",
    device_uuid: str = "",
) -> dict:
    import requests
    import json
    import os
    import tempfile
    import re

    if not repo_url:
        return {"status": "error", "message": "repo_url is required"}
    if not pixel_id:
        return {"status": "error", "message": "pixel_id is required"}
    if not capi_token:
        return {"status": "error", "message": "capi_token is required (from Meta Events Manager)"}

    headers = {
        "X-Auth-Token": api_token,
        "Content-Type": "application/json",
        "X-Profile-Id": "default",
        "X-Agent-Id": "agent_extella_default",
    }

    dest_dir = os.path.join(tempfile.gettempdir(), "ads_capi_repo")

    def run_sub(expert_name, params, timeout=120, target=None):
        payload = {"expert_name": expert_name, "params": params, "timeout": timeout}
        if target:
            payload["target"] = target
        try:
            resp = requests.post(
                f"{base_url}/api/expert/run",
                headers=headers,
                json=payload,
                timeout=timeout + 15,
            )
            if resp.status_code != 200:
                return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:300]}"}
            data = resp.json()
            return data.get("result", data)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── Step 1: Clone repository ──────────────────────────────────────────────
    print("[1/5] Cloning repository...")
    clone_result = run_sub(
        "ads_git_clone",
        {"repo_url": repo_url, "dest_dir": dest_dir},
        timeout=120,
        target=device_uuid if device_uuid else None,
    )
    clone_out = str(clone_result)
    if "EXIT:1" in clone_out or "fatal:" in clone_out.lower():
        return {"status": "error", "step": "git_clone", "message": clone_out[:500]}

    # ── Step 2: Detect stack ──────────────────────────────────────────────────
    print("[2/5] Detecting tech stack...")
    stack = "unknown"
    stack_files = {
        "node": ["package.json"],
        "python": ["requirements.txt", "app.py", "manage.py", "pyproject.toml"],
        "php": ["composer.json", "index.php"],
    }
    for lang, files in stack_files.items():
        for f in files:
            check_path = os.path.join(dest_dir, f)
            if os.path.exists(check_path):
                stack = lang
                break
        if stack != "unknown":
            break

    print(f"  Detected stack: {stack}")

    # ── Step 3: Generate CAPI integration file ────────────────────────────────
    print("[3/5] Generating CAPI integration code...")

    if stack == "node":
        file_path = os.path.join(dest_dir, "lib", "meta_capi.js")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        content = _gen_node_capi(pixel_id, capi_token)
    elif stack == "python":
        file_path = os.path.join(dest_dir, "meta_capi.py")
        content = _gen_python_capi(pixel_id, capi_token)
    elif stack == "php":
        os.makedirs(os.path.join(dest_dir, "app", "Services"), exist_ok=True)
        file_path = os.path.join(dest_dir, "app", "Services", "MetaCapi.php")
        content = _gen_php_capi(pixel_id, capi_token)
    else:
        # fallback: Node.js pattern
        stack = "node (fallback)"
        file_path = os.path.join(dest_dir, "meta_capi.js")
        content = _gen_node_capi(pixel_id, capi_token)

    with open(file_path, "w", encoding="utf-8") as fh:
        fh.write(content)

    rel_path = os.path.relpath(file_path, dest_dir)
    print(f"  Written: {rel_path}")

    # ── Step 4: Commit and push ───────────────────────────────────────────────
    print("[4/5] Creating branch and pushing...")
    commit_result = run_sub(
        "ads_git_commit_push",
        {
            "repo_dir": dest_dir,
            "branch": "capi-integration",
            "commit_msg": "feat: add Meta Conversions API (CAPI) server-side event tracking",
        },
        timeout=120,
        target=device_uuid if device_uuid else None,
    )
    commit_out = str(commit_result)
    if "EXIT:1" in commit_out and "nothing to commit" not in commit_out.lower():
        return {"status": "error", "step": "git_push", "message": commit_out[:500]}

    # ── Step 5: Create GitHub PR (optional) ──────────────────────────────────
    pr_url = None
    if github_token:
        print("[5/5] Creating GitHub pull request...")
        match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", repo_url)
        if match:
            owner, repo_name = match.group(1), match.group(2)
            pr_resp = requests.post(
                f"https://api.github.com/repos/{owner}/{repo_name}/pulls",
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github+json",
                },
                json={
                    "title": "Add Meta CAPI for server-side conversion tracking",
                    "head": "capi-integration",
                    "base": "main",
                    "body": (
                        f"Adds server-side event sending to Meta Conversions API.\n\n"
                        f"**Pixel ID**: `{pixel_id}`\n\n"
                        f"**Required environment variables**:\n"
                        f"- `META_PIXEL_ID={pixel_id}`\n"
                        f"- `META_CAPI_TOKEN=<your_capi_token>`\n\n"
                        f"Generated CAPI helper: `{rel_path}`\n\n"
                        f"After merging, verify events in Meta Events Manager → Test Events."
                    ),
                },
                timeout=30,
            )
            if pr_resp.status_code in (200, 201):
                pr_url = pr_resp.json().get("html_url")
            else:
                pr_url = f"PR creation failed: {pr_resp.text[:200]}"
    else:
        pr_url = None
        print("[5/5] No GitHub token — skipping PR creation (branch pushed to origin)")

    return {
        "status": "success",
        "stack": stack,
        "file_created": rel_path,
        "branch": "capi-integration",
        "pr_url": pr_url,
        "message": (
            f"CAPI integration ({stack}) committed to branch 'capi-integration'. "
            + (f"PR: {pr_url}" if pr_url and pr_url.startswith("http") else
               "Review and merge the branch manually.")
        ),
    }


# ── Code generators ───────────────────────────────────────────────────────────

def _gen_node_capi(pixel_id: str, capi_token: str) -> str:
    return f"""// lib/meta_capi.js — Meta Conversions API helper (auto-generated)
const crypto = require('crypto');
const https = require('https');

const PIXEL_ID = process.env.META_PIXEL_ID || '{pixel_id}';
const ACCESS_TOKEN = process.env.META_CAPI_TOKEN || '{capi_token}';
const API_VERSION = 'v25.0';

function hashData(value) {{
  if (!value) return null;
  return crypto.createHash('sha256').update(String(value).trim().toLowerCase()).digest('hex');
}}

async function sendEvent({{ eventName, eventTime, userData = {{}}, customData = {{}}, eventSourceUrl }}) {{
  const payload = {{
    data: [{{
      event_name: eventName,
      event_time: eventTime || Math.floor(Date.now() / 1000),
      event_source_url: eventSourceUrl,
      action_source: 'website',
      user_data: Object.fromEntries(
        Object.entries({{
          em: userData.email ? hashData(userData.email) : undefined,
          ph: userData.phone ? hashData(userData.phone) : undefined,
          client_ip_address: userData.ip,
          client_user_agent: userData.userAgent,
          fbp: userData.fbp,
          fbc: userData.fbc,
        }}).filter(([, v]) => v != null)
      ),
      custom_data: customData,
    }}],
  }};

  return new Promise((resolve, reject) => {{
    const body = JSON.stringify(payload);
    const req = https.request({{
      hostname: 'graph.facebook.com',
      path: `/${{API_VERSION}}/${{PIXEL_ID}}/events?access_token=${{ACCESS_TOKEN}}`,
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) }},
    }}, (res) => {{
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(JSON.parse(data)));
    }});
    req.on('error', reject);
    req.write(body);
    req.end();
  }});
}}

module.exports = {{ sendEvent, hashData }};
"""


def _gen_python_capi(pixel_id: str, capi_token: str) -> str:
    return f"""# meta_capi.py — Meta Conversions API helper (auto-generated)
import hashlib
import time
import os
import requests

PIXEL_ID = os.environ.get("META_PIXEL_ID", "{pixel_id}")
ACCESS_TOKEN = os.environ.get("META_CAPI_TOKEN", "{capi_token}")
API_VERSION = "v25.0"
ENDPOINT = f"https://graph.facebook.com/{{API_VERSION}}/{{PIXEL_ID}}/events"


def _hash(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def send_event(
    event_name: str,
    user_data: dict = None,
    custom_data: dict = None,
    event_source_url: str = "",
    event_time: int = None,
) -> dict:
    user_data = user_data or {{}}
    custom_data = custom_data or {{}}
    payload = {{
        "data": [{{
            "event_name": event_name,
            "event_time": event_time or int(time.time()),
            "event_source_url": event_source_url,
            "action_source": "website",
            "user_data": {{
                k: v for k, v in {{
                    "em": _hash(user_data.get("email", "")),
                    "ph": _hash(user_data.get("phone", "")),
                    "client_ip_address": user_data.get("ip"),
                    "client_user_agent": user_data.get("user_agent"),
                    "fbp": user_data.get("fbp"),
                    "fbc": user_data.get("fbc"),
                }}.items() if v
            }},
            "custom_data": custom_data,
        }}],
        "access_token": ACCESS_TOKEN,
    }}
    try:
        resp = requests.post(ENDPOINT, json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        return {{"error": str(e)}}
"""


def _gen_php_capi(pixel_id: str, capi_token: str) -> str:
    return f"""<?php
// app/Services/MetaCapi.php — Meta Conversions API helper (auto-generated)
namespace App\\Services;

class MetaCapi
{{
    private string $pixelId;
    private string $accessToken;
    private string $apiVersion = 'v25.0';

    public function __construct()
    {{
        $this->pixelId = env('META_PIXEL_ID', '{pixel_id}');
        $this->accessToken = env('META_CAPI_TOKEN', '{capi_token}');
    }}

    private function hash(string $value): string
    {{
        return hash('sha256', strtolower(trim($value)));
    }}

    public function sendEvent(string $eventName, array $userData = [], array $customData = [], string $eventSourceUrl = ''): array
    {{
        $payload = [
            'data' => [[
                'event_name'       => $eventName,
                'event_time'       => time(),
                'event_source_url' => $eventSourceUrl,
                'action_source'    => 'website',
                'user_data'        => array_filter([
                    'em'                => !empty($userData['email']) ? $this->hash($userData['email']) : null,
                    'ph'                => !empty($userData['phone']) ? $this->hash($userData['phone']) : null,
                    'client_ip_address' => $userData['ip'] ?? null,
                    'client_user_agent' => $userData['user_agent'] ?? null,
                    'fbp'               => $userData['fbp'] ?? null,
                    'fbc'               => $userData['fbc'] ?? null,
                ]),
                'custom_data' => $customData,
            ]],
            'access_token' => $this->accessToken,
        ];

        $ch = curl_init("https://graph.facebook.com/{{$this->apiVersion}}/{{$this->pixelId}}/events");
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => json_encode($payload),
            CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 10,
        ]);
        $result = curl_exec($ch);
        curl_close($ch);
        return json_decode($result, true) ?? [];
    }}
}}
"""
