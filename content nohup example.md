# ═══════════════════════════════════════════════════════════════
# NOHUP EXPERT — это НЕ функция, а Python-скрипт верхнего уровня
# НЕТ: def expert_name(...)
# НЕТ: $extens / include()
# Kwargs доступны через {{placeholder}} подстановку
# ═══════════════════════════════════════════════════════════════

import os
import json
import time
import requests
from pathlib import Path

# ── Kwargs через {{placeholder}} подстановку ──────────────────
api_token   = "{{api_token}}"    # инжектируется агентом
base_url    = "{{base_url}}"     # https://api.extella.ai
input_text  = "{{input_text}}"
chat_id     = "{{chat_id}}"
bot_token   = "{{bot_token}}"

# ── Хелпер: вызов суб-эксперта через REST API ─────────────────
def call_expert(name: str, params: dict) -> dict:
    """Вызывает суб-эксперт через /api/expert/run."""
    try:
        resp = requests.post(
            f"{base_url}/api/expert/run",
            headers={
                "X-Auth-Token": api_token,
                "Content-Type": "application/json"
            },
            json={"expert_name": name, "params": params},
            timeout=120
        )
        if resp.status_code != 200:
            return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ── Оркестрация: шаги выполняются последовательно ─────────────
print("[1/4] 🔄 Шаг 1: Транскрибируем аудио...")
step1 = call_expert("audio_transcribe", {
    "audio_path": input_text,
    "api_key": "{{ openai_api_key }}"
})
if step1.get("status") != "success":
    result = {"status": "error", "step": "transcribe", "details": step1}
else:
    transcript = step1.get("result", {}).get("text", "")
    print(f"[2/4] 🧠 Шаг 2: Суммаризируем текст ({len(transcript)} chars)...")
    
    step2 = call_expert("summarize_text", {
        "text": transcript,
        "length": "short"
    })
    
    summary = step2.get("result", {}).get("summary", transcript[:500])
    print("[3/4] 📤 Шаг 3: Отправляем в Telegram...")
    
    step3 = call_expert("send_telegram_message", {
        "chat_id": chat_id,
        "message": f"<b>Резюме:</b>\n\n{summary}",
        "bot_token": bot_token,
        "parse_mode": "HTML"
    })
    
    result = {
        "status": "success",
        "transcript_length": len(transcript),
        "summary_length": len(summary),
        "telegram_sent": step3.get("status") == "success"
    }

# ── Сохранение результата в файл (return не работает в nohup) ─
print("[4/4] 💾 Сохранение результата...")
output_path = Path("/tmp/nohup_audio_pipeline_result.json")
output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(f"✅ Готово. Результат: {output_path}")
Как сохраняется через API:{
  "name": "audio_summary_pipeline",
  "description": "Orchestrates audio transcription → summarization → Telegram delivery. Parameters: api_token — Extella API token; base_url — API base URL; input_text — path to audio file; chat_id — Telegram chat ID; bot_token — Telegram bot token; openai_api_key — OpenAI key for transcription.",
  "code": "<скрипт выше>",
  "kwargs": {
    "api_token": "",
    "base_url": "https://api.extella.ai",
    "input_text": "",
    "chat_id": "",
    "bot_token": "",
    "openai_api_key": ""
  },
  "cspl": "nohup"
}
Ключевые отличия от fython:Aspectfython (обычный)nohup (оркестратор)Формат телаdef expert(...) + $extensPython-скрипт, без defKwargsПараметры функции{{placeholder}} подстановкаВозвратreturn {...}Запись в /tmp/*.jsonВызов других❌ Нельзя✅ Только через /api/expert/runВремя жизниОдин чат-турнФоновый процесс, живёт дольшеВозвращает сразуРезультат{pid, log_file, pid_file}