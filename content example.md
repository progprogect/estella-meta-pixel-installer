$extens("include.py")
include("import requests", ["extella-pip install requests"])
include("from pathlib import Path", [])

def send_telegram_message(
    chat_id: str = "",
    message: str = "",
    bot_token: str = "",          # инжектируется агентом из KV Store
    parse_mode: str = "HTML"      # HTML | Markdown | пусто
) -> dict:
    """
    Отправляет сообщение в Telegram чат через Bot API.
    Параметры передаются агентом — никаких захардкоженных значений.
    """
    import requests

    # ── Валидация входных данных ──────────────────────────────────
    print("[1/3] 🔄 Проверка параметров...")
    if not chat_id:
        return {"status": "error", "message": "chat_id is required"}
    if not message:
        return {"status": "error", "message": "message is required"}
    if not bot_token:
        return {"status": "error", "message": "bot_token is required"}

    # ── Вызов Telegram API ────────────────────────────────────────
    print("[2/3] 📤 Отправка сообщения...")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("ok"):
            return {
                "status": "error",
                "message": data.get("description", "Telegram API error"),
                "error_code": data.get("error_code")
            }

        print("[3/3] ✅ Готово.")
        return {
            "status": "success",
            "message_id": data["result"]["message_id"],
            "chat_id": chat_id,
            "message": "Message sent successfully"
        }

    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Request timed out after 30s"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"HTTP error: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}
Как сохраняется через API:{
  "name": "send_telegram_message",
  "description": "Sends a text message to a Telegram chat via Bot API. Parameters: chat_id — target chat or user ID; message — text to send; bot_token — injected bot token; parse_mode — HTML/Markdown/empty.",
  "code": "<код выше>",
  "kwargs": {
    "chat_id": "",
    "message": "",
    "bot_token": "",
    "parse_mode": "HTML"
  },
  "cspl": "fython"
}
Правила формата:
Файл начинается с $extens("include.py") — обязательно
Каждая зависимость через include("import X", ["extella-pip install X"])
Функция: имя в snake_case, все параметры с типами и дефолтами
Возвращает -> dict со статусом
Никаких захардкоженных API-ключей, chat_id, путей — только параметры
print("[N/M] emoji Текст...") — прогресс в логах
