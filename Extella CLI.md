# Extella CLI — Полное руководство по работе через командную строку

## Содержание
1. [Что такое Extella API](#1-что-такое-extella-api)
2. [Аутентификация — получение токена](#2-аутентификация--получение-токена)
3. [Запуск эксперта](#3-запуск-эксперта)
4. [Поиск экспертов](#4-поиск-экспертов)
5. [Получение информации об эксперте](#5-получение-информации-об-эксперте)
6. [Сохранение эксперта](#6-сохранение-эксперта)
7. [KV Store — хранение данных](#7-kv-store--хранение-данных)
8. [Концепты — база знаний](#8-концепты--база-знаний)
9. [Асинхронное выполнение](#9-асинхронное-выполнение)
10. [Python SDK (обёртка)](#10-python-sdk-обёртка)
11. [Bash-алиасы и удобные команды](#11-bash-алиасы-и-удобные-команды)
12. [Типичные сценарии использования](#12-типичные-сценарии-использования)
13. [Коды ошибок и отладка](#13-коды-ошибок-и-отладка)

---

## 1. Что такое Extella API

Extella предоставляет REST API для выполнения «экспертов» — атомарных Python-функций, хранящихся в облачной библиотеке. Каждый эксперт принимает именованные параметры (`kwargs`) и возвращает JSON.

**Base URL:**
https://api.extella.ai
**Два режима выполнения:**

| Режим | Как задаётся | Где выполняется |
|-------|-------------|-----------------|
| **Serverless** | без параметра `target` | На удалённых воркерах Extella (интернет, /tmp) |
| **Local (устройство)** | с параметром `target: "<device_uuid>"` | На вашем Mac/Windows/Linux через Extella Desktop |

---

## 2. Аутентификация — получение токена

Переменная окружения в документации ниже — **`EXTELLA_TOKEN`**. В сценариях `curl` и SDK используйте её или задайте **`EXTELLA_API_TOKEN`** тем же значением (так названа переменная в скрипте публикации пресета `preset_floorplan/scripts/bootstrap_api.py`).

### Генерация токена через API

```bash
curl -X POST https://api.extella.ai/api/token/generate \
  -H "Content-Type: application/json" \
  -d '{"name": "my-cli-token"}'
Ответ:{
  "status": "success",
  "token": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "user_id": "your_user_id",
  "name": "my-cli-token"
}
Настройка переменной окружения# ~/.zshrc или ~/.bashrc
export EXTELLA_TOKEN="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
Валидация токенаcurl -X POST https://api.extella.ai/api/token/validate \
  -H "Content-Type: application/json" \
  -d '{"token": "'$EXTELLA_TOKEN'"}'
Ответ при успехе:{"status": "success", "valid": true, "user_id": "your_user_id"}
3. Запуск экспертаБазовый запуск (serverless)curl -X POST https://api.extella.ai/api/expert/run \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "expert_name": "get_joke",
    "params": {
      "category": "programming"
    }
  }'
Ответ:{
  "status": "success",
  "expert_name": "get_joke",
  "result": {
    "status": "success",
    "joke": { "type": "single", "joke": "Why do programmers prefer dark mode?..." }
  },
  "execution_log": ["Running get_joke...", "Done."],
  "run_time_ms": 423
}
Запуск на локальном устройствеcurl -X POST https://api.extella.ai/api/expert/run \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "expert_name": "read_file_content",
    "params": {
      "file_path": "~/Downloads/report.pdf"
    },
    "target": "YOUR_DEVICE_UUID"
  }'

Важно: target — UUID устройства из Extella Desktop. Без него эксперт выполняется на удалённом воркере (без доступа к вашей файловой системе).
Асинхронный запускcurl -X POST https://api.extella.ai/api/expert/run \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "expert_name": "long_running_task",
    "params": {"input": "data"},
    "wait": false
  }'
Ответ:{
  "status": "success",
  "task_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
Проверка статуса задачиcurl -X POST https://api.extella.ai/api/task/check \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"}'
4. Поиск экспертовСемантический поиск по названию и описанию.curl -X POST https://api.extella.ai/api/blocks/search \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "send telegram message",
    "limit": 10
  }'
Ответ:{
  "status": "success",
  "matches": [
    {
      "name": "send_telegram_message",
      "description": "Sends a message to Telegram...",
      "score": 98,
      "kwargs": {
        "chat_id": "",
        "message": "",
        "bot_token_key": "telegram_bot_token"
      }
    }
  ],
  "total": 1,
  "search_time_ms": 45.2
}
5. Получение информации об экспертеcurl -X POST https://api.extella.ai/api/expert/get \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "send_telegram_message"}'
Ответ:{
  "status": "success",
  "expert_name": "send_telegram_message",
  "expert_description": "Sends a message to Telegram chat...",
  "expert_params": {
    "chat_id": "",
    "message": "",
    "bot_token_key": "telegram_bot_token",
    "parse_mode": ""
  },
  "cspl": "fython",
  "createdAt": "2026-04-01T12:00:00Z"
}

Важно: Поле expert_code не возвращается по соображениям безопасности. Используйте expert_params для понимания аргументов.
6. Сохранение экспертаcurl -X POST https://api.extella.ai/api/expert/save \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my_expert",
    "description": "Does something useful. Parameters: input_text — text to process; language — output language.",
    "code": "$extens(\"include.py\")\ninclude(\"import requests\", [\"extella-pip install requests\"])\n\ndef my_expert(input_text: str = \"\", language: str = \"en\") -> dict:\n    import requests\n    return {\"status\": \"success\", \"result\": input_text.upper()}",
    "kwargs": {
      "input_text": "",
      "language": "en"
    },
    "cspl": "fython"
  }'
Обязательные поля экспертаПолеТипОписаниеnamestringsnake_case, уникальный идентификаторdescriptionstringНа английском, включает описание всех kwargscodestringPython-код, начинается с $extens("include.py")kwargsobjectПараметры с дефолтными значениямиcsplstring"fython" (стандарт) или "nohup" (долгие задачи)Удаление экспертаcurl -X DELETE "https://api.extella.ai/api/expert/delete/my_expert" \
  -H "X-Auth-Token: $EXTELLA_TOKEN"
7. KV Store — хранение данныхKV Store — персистентное хранилище ключ-значение с семантическим поиском. Используется для хранения API-ключей, конфигов, токенов.Запись значенияcurl -X POST https://api.extella.ai/api/kv/set \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "openai_api_key",
    "value": "sk-...",
    "description": "OpenAI API key for GPT-4"
  }'
Чтение значенияcurl -X POST https://api.extella.ai/api/kv/get \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"key": "openai_api_key"}'
Ответ:{
  "status": "success",
  "key": "openai_api_key",
  "value": "sk-...",
  "description": "OpenAI API key for GPT-4"
}
Семантический поиск по KVcurl -X POST https://api.extella.ai/api/kv/search \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "telegram bot token", "limit": 5}'
Список всех ключейcurl -X POST https://api.extella.ai/api/kv/list \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
Удаление ключаcurl -X POST https://api.extella.ai/api/kv/remove \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"key": "openai_api_key"}'
8. Концепты — база знанийКонцепты — это персистентная база знаний с семантическим поиском (pgvector). Используется для хранения технических паттернов, решений ошибок, конфигураций.Добавление концептаcurl -X POST https://api.extella.ai/api/concept/add \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "For OCR use Google Vision API. Works best with scanned documents, supports 50+ languages."}'
Семантический поиск концептовcurl -X POST https://api.extella.ai/api/concept/search \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "OCR image text recognition", "limit": 5}'
Список всех концептовcurl -X POST https://api.extella.ai/api/concept/list \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
Обновление концептаcurl -X POST https://api.extella.ai/api/concept/update \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "concept_id": 42,
    "new_text": "For OCR use Google Vision API or Tesseract. Vision API is more accurate."
  }'
Удаление концептаcurl -X POST https://api.extella.ai/api/concept/remove \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"concept_id": 42}'
9. Асинхронное выполнениеДля долгих задач (>30 сек) используйте "wait": false + поллинг через task/check.Паттерн асинхронного запуска# 1. Запустить асинхронно
TASK_ID=$(curl -s -X POST https://api.extella.ai/api/expert/run \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"expert_name": "long_task", "params": {}, "wait": false}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")

echo "Task ID: $TASK_ID"

# 2. Поллить статус
while true; do
  STATUS=$(curl -s -X POST https://api.extella.ai/api/task/check \
    -H "X-Auth-Token: $EXTELLA_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"task_id\": \"$TASK_ID\"}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('status', 'unknown'))")
  
  echo "Status: $STATUS"
  
  if [ "$STATUS" = "running" ]; then
    echo "Done!"
    break
  fi
  
  sleep 5
done
Статусы задачиСтатусЗначениеrunningУстройство готово / задача завершенаbusyУстройство занято, выполняет задачу10. Python SDK (обёртка)Создайте файл extella_client.py в своём проекте:import requests
import time
import os
from typing import Optional

class ExtellaClient:
    BASE_URL = "https://api.extella.ai"
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("EXTELLA_TOKEN", "")
        if not self.token:
            raise ValueError("EXTELLA_TOKEN is required")
        self.headers = {
            "X-Auth-Token": self.token,
            "Content-Type": "application/json"
        }
    
    def run_expert(
        self,
        expert_name: str,
        params: dict = None,
        target: str = None,
        timeout: int = 120,
        wait: bool = True
    ) -> dict:
        """Run an expert and return the result."""
        payload = {
            "expert_name": expert_name,
            "params": params or {},
            "wait": wait
        }
        if target:
            payload["target"] = target
        
        r = requests.post(
            f"{self.BASE_URL}/api/expert/run",
            headers=self.headers,
            json=payload,
            timeout=timeout + 10
        )
        r.raise_for_status()
        return r.json()
    
    def run_expert_async(self, expert_name: str, params: dict = None, target: str = None) -> str:
        """Run expert asynchronously, return task_id."""
        result = self.run_expert(expert_name, params, target, wait=False)
        task_id = result.get("task_id")
        if not task_id:
            raise RuntimeError(f"No task_id in response: {result}")
        return task_id
    
    def wait_for_task(self, task_id: str, poll_interval: int = 5, max_wait: int = 300) -> dict:
        """Poll until task is done."""
        elapsed = 0
        while elapsed < max_wait:
            r = requests.post(
                f"{self.BASE_URL}/api/task/check",
                headers=self.headers,
                json={"task_id": task_id},
                timeout=15
            )
            data = r.json()
            if data.get("status") == "running":
                return data
            time.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(f"Task {task_id} timed out after {max_wait}s")
    
    def search_experts(self, query: str, limit: int = 10) -> list:
        """Semantic search for experts."""
        r = requests.post(
            f"{self.BASE_URL}/api/blocks/search",
            headers=self.headers,
            json={"query": query, "limit": limit},
            timeout=15
        )
        r.raise_for_status()
        return r.json().get("matches", [])
    
    def kv_set(self, key: str, value: str, description: str = "") -> dict:
        r = requests.post(
            f"{self.BASE_URL}/api/kv/set",
            headers=self.headers,
            json={"key": key, "value": value, "description": description},
            timeout=10
        )
        r.raise_for_status()
        return r.json()
    
    def kv_get(self, key: str) -> Optional[str]:
        r = requests.post(
            f"{self.BASE_URL}/api/kv/get",
            headers=self.headers,
            json={"key": key},
            timeout=10
        )
        if r.status_code == 200:
            return r.json().get("value")
        return None
    
    def kv_search(self, query: str, limit: int = 5) -> list:
        r = requests.post(
            f"{self.BASE_URL}/api/kv/search",
            headers=self.headers,
            json={"query": query, "limit": limit},
            timeout=10
        )
        r.raise_for_status()
        return r.json().get("results", [])


# ── Использование ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    client = ExtellaClient()  # читает EXTELLA_TOKEN из env
    
    # Запустить эксперта
    result = client.run_expert("get_joke", {"category": "programming"})
    print(result["result"])
    
    # Поиск экспертов
    matches = client.search_experts("send telegram message", limit=5)
    for m in matches:
        print(f"{m['name']}: {m['description'][:60]}...")
    
    # Сохранить API-ключ
    client.kv_set("my_api_key", "sk-...", "My OpenAI key")
    
    # Прочитать API-ключ и передать в эксперта
    api_key = client.kv_get("openai_api_key")
    result = client.run_expert("call_gpt4", {
        "prompt": "Hello!",
        "api_key": api_key
    })
11. Bash-алиасы и удобные командыДобавьте в ~/.zshrc или ~/.bashrc:# Base
export EXTELLA_TOKEN="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export EXTELLA_URL="https://api.extella.ai"

# Запустить эксперта: extella_run get_joke '{"category": "programming"}'
extella_run() {
  local expert=\$1
  local params=${2:-"{}"}
  curl -s -X POST "$EXTELLA_URL/api/expert/run" \
    -H "X-Auth-Token: $EXTELLA_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"expert_name\": \"$$expert\", \"params\": $$params}" \
    | python3 -m json.tool
}

# Поиск экспертов: extella_search "translate text"
extella_search() {
  curl -s -X POST "$EXTELLA_URL/api/blocks/search" \
    -H "X-Auth-Token: $EXTELLA_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"\$1\", \"limit\": 10}" \
    | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('matches', []):
    print(f\"{m['score']:3d}  {m['name']:<35} {m['description'][:60]}...\")
"
}

# Читать из KV: extella_kv_get openai_api_key
extella_kv_get() {
  curl -s -X POST "$EXTELLA_URL/api/kv/get" \
    -H "X-Auth-Token: $EXTELLA_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"key\": \"\$1\"}" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('value','NOT FOUND'))"
}

# Записать в KV: extella_kv_set my_key "my_value"
extella_kv_set() {
  curl -s -X POST "$EXTELLA_URL/api/kv/set" \
    -H "X-Auth-Token: $EXTELLA_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"key\": \"\$1\", \"value\": \"\$2\"}" \
    | python3 -m json.tool
}

# Health check
extella_health() {
  curl -s "$EXTELLA_URL/api/health" | python3 -m json.tool
}
После добавления: source ~/.zshrc12. Типичные сценарии использованияСценарий 1: Запустить эксперта и получить результатfrom extella_client import ExtellaClient

client = ExtellaClient()

# Простой запрос
result = client.run_expert("send_telegram_message", {
    "chat_id": "123456789",
    "message": "Hello from CLI!",
    "bot_token": "YOUR_BOT_TOKEN"
})

if result.get("result", {}).get("status") == "success":
    print("Message sent!")
else:
    print("Error:", result)
Сценарий 2: Передача API-ключа через KV Storeclient = ExtellaClient()

# Получить ключ из хранилища
api_key = client.kv_get("openai_api_key")

# Передать ключ напрямую в параметрах (эксперт не читает KV сам)
result = client.run_expert("call_openai_api", {
    "prompt": "Translate to English: Привет мир",
    "api_key": api_key,
    "model": "gpt-4o"
})

print(result["result"]["response"])
Сценарий 3: Работа с локальными файламиclient = ExtellaClient()

# ВАЖНО: для локальных файлов нужен target (UUID устройства)
DEVICE_UUID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

result = client.run_expert(
    "read_file_content",
    {"file_path": "~/Downloads/report.pdf"},
    target=DEVICE_UUID
)

content = result["result"]["content"]
print(content[:500])
Сценарий 4: Пакетный запуск через циклclient = ExtellaClient()
items = ["apple", "banana", "cherry"]

for item in items:
    result = client.run_expert("translate_text", {
        "text": item,
        "target_language": "ru",
        "api_key": client.kv_get("openai_api_key")
    })
    translation = result.get("result", {}).get("translated", "")
    print(f"{item} → {translation}")
Сценарий 5: Создание и запуск нового экспертаclient = ExtellaClient()

CODE = '''
$extens("include.py")
include("import requests", ["extella-pip install requests"])

def my_new_expert(url: str = "", timeout: int = 10) -> dict:
    import requests
    try:
        r = requests.get(url, timeout=timeout)
        return {"status": "success", "status_code": r.status_code, "ok": r.ok}
    except Exception as e:
        return {"status": "error", "message": str(e)}
'''

# Сохранить эксперта
requests_lib = __import__("requests")
requests_lib.post(
    "https://api.extella.ai/api/expert/save",
    headers={"X-Auth-Token": client.token, "Content-Type": "application/json"},
    json={
        "name": "check_url_status",
        "description": "Checks HTTP status of a URL. Parameters: url — URL to check; timeout — request timeout in seconds.",
        "code": CODE,
        "kwargs": {"url": "", "timeout": 10},
        "cspl": "fython"
    }
)

# Запустить
result = client.run_expert("check_url_status", {"url": "https://example.com"})
print(result)
13. Коды ошибок и отладкаСтруктура ошибок{
  "status": "error",
  "message": "Expert not found: my_typo_expert"
}
Типичные ошибкиСитуацияСимптомРешениеНеверный токенHTTP 401Проверить EXTELLA_TOKENЭксперт не найден"Expert not found"Проверить имя через search_expertsТаймаут"Expert timed out"Увеличить timeout или использовать wait=falseФайл не найден"No such file or directory"Проверить target (локальные файлы требуют устройства)Ключ не найден в KVvalue = nullСоздать ключ через kv_setЗашифрованный ключ"$enc:..." в значенииРазблокировать KV через PIN в Extella DesktopПроверка выполнения экспертаВсегда проверяйте execution_log на наличие ошибок:result = client.run_expert("my_expert", {...})

# Проверка на ошибки
if "error" in result:
    print("FAILED:", result["error"])
elif result.get("status") != "success":
    print("UNCLEAR:", result)
elif "execution_log" in result:
    log_text = str(result["execution_log"])
    if any(x in log_text.lower() for x in ["error:", "exception", "failed"]):
        print("ERROR IN LOGS:", log_text)
    else:
        print("SUCCESS:", result["result"])
Health Checkcurl https://api.extella.ai/api/health
{"status": "success", "experts_db_available": true}
Краткая шпаргалка# Запустить эксперта
curl -X POST https://api.extella.ai/api/expert/run \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"expert_name": "NAME", "params": {"key": "value"}}'

# Найти эксперта
curl -X POST https://api.extella.ai/api/blocks/search \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "what I need", "limit": 10}'

# Читать KV
curl -X POST https://api.extella.ai/api/kv/get \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"key": "my_key"}'

# Писать KV
curl -X POST https://api.extella.ai/api/kv/set \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"key": "my_key", "value": "my_value", "description": "..."}'

# Проверить статус задачи
curl -X POST https://api.extella.ai/api/task/check \
  -H "X-Auth-Token: $EXTELLA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task_id": "TASK_UUID"}'

---

## 14. Пресет планов (floorplan) и типичные сбои

Этот раздел относится к репозиторию **plan-creation-preset** (`preset_floorplan/`).

| Симптом | Причина | Что делать |
|--------|---------|------------|
| В логе выполнения первая функция не та (`_draft_rooms_poly_ok`, `_units_label`, …) | У **fython** точка входа — первая top-level **`def`** в файле; встроенный merge/core шёл раньше имени эксперта | Использовать актуальные тела из репозитория (шим первой функции = имя эксперта); пересобрать: `python3 preset_floorplan/scripts/embed_experts.py` и снова `bootstrap_api.py` |
| Файлы не в настоящих «Загрузках», путь вида `.../~/Downloads/` | Раньше **`~` не раскрывался** | В параметре **`output_dir`** можно указывать `~/Downloads` — в пресете путь обрабатывается через **`expanduser`**; либо давайте **абсолютный** путь |
| **`Target … is unavailable` (HTTP 500 при `expert/run`)** | В профиле агента задано **локальное устройство** (Extella Desktop), оно **офлайн** | Включить Desktop на том UUID или в настройках агента выполнять экспертов **без привязки к устройству** (serverless), если политика аккаунта позволяет |
| Нет PDF с вектором, только fallback PNG | Нет **Cairo/CairoSVG** на воркере | Ожидаемо на части сред; **SVG** в выводе обычно есть; для PDF — окружение с Cairo или локальный target |
| Агент запускает подряд **`floorplan_openai_layout`** и **`floorplan_full_openai_pipeline`** | В концепте раньше выглядело как «список шагов» | Для текста ТЗ — **только** `floorplan_full_openai_pipeline`; layout отдельно — только для явной пошаговой отладки |
| Плохие / странные картинки узлов | Только **DALL·E 3** или короткий промпт | По умолчанию **`gpt-image-1.5`**; **`gpt-image-2`** — при прошедшей верификации org. Резерв **`dall-e-3`**. Не путать с **GPT‑2** (текст) |
| **`gpt-image-2` → HTTP 403** | Ключ/организация без доступа к новейшей модели | Верификация на [platform.openai.com](https://platform.openai.com/settings/organization/general) или **`image_model`: `gpt-image-1.5`** ([документация](https://developers.openai.com/api/docs/models/gpt-image-1.5)) |
| DALL·E 3 ругается на **size** | Для **dall-e-3** допустимы только **1024×1024**, **1792×1024**, **1024×1792** | Пресет подставляет **1792×1024**, если запрошен ландшафтный 1536×1024 |
| Итоговый PNG «рвётся» | Растр из SVG (Cairo + вложенные PNG) | **`final_png_from_openai: true`** — **`paths.png`** из OpenAI; **`paths.svg`** — геометрия. **`false`** — снова PNG из вектора |

Документация: [GPT Image 1.5](https://developers.openai.com/api/docs/models/gpt-image-1.5), [GPT Image 2](https://developers.openai.com/api/docs/models/gpt-image-2).

Публикация пресета в Extella: переменная **`EXTELLA_API_TOKEN`** (то же значение, что и **`EXTELLA_TOKEN`** в примерах выше), скрипт `preset_floorplan/scripts/bootstrap_api.py`.

**Ответ `POST /api/expert/run`:** при **`wait: false`** поле **`result`** иногда приходит **строкой** с Python-представлением dict (как у `repr()`), а не JSON. Для разбора удобно **`ast.literal_eval(result)`** (после проверки, что строка начинается с `{`). Опрос **`/api/task/check`** в части окружений даёт **404** — надёжнее для длинных задач снова вызывать **`wait: false`** с увеличенным HTTP-timeout клиента или повторять запрос из UI.
