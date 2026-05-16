# Extella API Reference
Base URL: `https://api.extella.ai`
Auth: `X-Auth-Token: <your_token>` в заголовке КАЖДОГО запроса

---

## 🤖 EXPERTS API

### Сохранить / обновить эксперт
POST /api/expert/save```json
{
  "name": "send_telegram_message",
  "description": "Sends message to Telegram. Parameters: chat_id — ...; message — ...; bot_token — ...",
  "code": "$extens(\"include.py\")\ninclude(\"import requests\", [\"extella-pip install requests\"])\n\ndef send_telegram_message(...) -> dict:\n    ...",
  "kwargs": {
    "chat_id": "",
    "message": "",
    "bot_token": "",
    "parse_mode": "HTML"
  },
  "cspl": "fython"
}
Ответ:{ "status": "success", "expert_name": "send_telegram_message", "user_id": "john_a1b2c3d4" }
Запустить экспертPOST /api/expert/run
{
  "expert_name": "send_telegram_message",
  "params": {
    "chat_id": "123456789",
    "message": "Hello!",
    "bot_token": "7654321:AABBcc..."
  }
}
Синхронный ответ (wait=true, по умолчанию):{
  "status": "success",
  "expert_name": "send_telegram_message",
  "result": {"status": "success", "message_id": 42},
  "execution_log": ["[1/3] 🔄 Проверка...", "[2/3] 📤 Отправка...", "[3/3] ✅ Готово."]
}
Асинхронный ответ (wait=false):{ "task_id": "uuid-1234-..." }
Параметры запуска:ПараметрТипОписаниеexpert_namestringИмя экспертаparamsobjectkwargs для экспертаtargetstringUUID устройства (только для удалённого запуска)waitboolЖдать результата (default: true)isolatedboolЗапуск в изолированном venvtimeoutintТаймаут в секундахПолучить экспертGET /api/expert/get/<name>
Ответ:{
  "status": "success",
  "expert_name": "send_telegram_message",
  "expert_description": "Sends message to Telegram...",
  "expert_code": "...",
  "expert_params": {"chat_id": "", "message": "", ...},
  "cspl": "fython",
  "createdAt": "2026-04-11T14:24:15Z"
}
Поиск экспертов (семантический)POST /api/blocks/search
{ "query": "send telegram notification", "limit": 50 }
Ответ:{
  "status": "success",
  "matches": [
    {
      "name": "send_telegram_message",
      "description": "Sends message to Telegram...",
      "score": 95,
      "kwargs": {"chat_id": "", "message": ""}
    }
  ],
  "total": 3
}
Удалить экспертDELETE /api/expert/delete/<name>
Проверить статус асинхронной задачиPOST /api/task/check
{ "task_id": "uuid-1234-..." }
Ответ:{ "status": "running" }   // или "busy"
🧠 CONCEPTS API (Долгосрочная память)Добавить концептPOST /api/concept/add
{ "text": "Для OCR сканов использовать pytesseract + pdf2image..." }
Ответ: { "status": "success", "id": 42, "text": "..." }Семантический поискPOST /api/concept/search
{ "query": "OCR PDF scanned document", "limit": 5 }
Ответ:{
  "status": "success",
  "results": [
    { "concept_id": 42, "concept_text": "Для OCR...", "similarity": 0.92 }
  ]
}
Обновить концептPOST /api/concept/update
{ "concept_id": 42, "new_text": "Обновлённый текст концепта..." }
Удалить концептPOST /api/concept/remove
{ "concept_id": 42 }
Список всех концептовGET /api/concept/list
🔑 KV STORE APIЗаписать ключPOST /api/kv/set
{
  "key": "openai_api_key",
  "value": "sk-...",
  "description": "OpenAI API key, personal account"
}
Получить ключPOST /api/kv/get
{ "key": "openai_api_key" }
Ответ: { "status": "success", "key": "openai_api_key", "value": "sk-...", "description": "..." }Семантический поиск по ключамPOST /api/kv/search
{ "query": "telegram bot token", "limit": 5 }
🔐 TOKEN APIСгенерировать токенPOST /api/token/generate
{ "name": "my_app_token" }
Ответ: { "status": "success", "token": "uuid-...", "user_id": "john_...", "name": "my_app_token" }Валидировать токенPOST /api/token/validate
{ "token": "uuid-..." }
🚀 Быстрый старт (curl)# 1. Запустить эксперт
curl -X POST https://api.extella.ai/api/expert/run \
  -H "X-Auth-Token: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "expert_name": "get_weather",
    "params": {"city": "Moscow", "api_key": "YOUR_OWM_KEY"}
  }'

# 2. Поиск эксперта
curl -X POST https://api.extella.ai/api/blocks/search \
  -H "X-Auth-Token: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "weather forecast city", "limit": 10}'

# 3. Добавить концепт
curl -X POST https://api.extella.ai/api/concept/add \
  -H "X-Auth-Token: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "OpenWeatherMap API endpoint: api.openweathermap.org/data/2.5/weather"}'

# 4. Найти концепт
curl -X POST https://api.extella.ai/api/concept/search \
  -H "X-Auth-Token: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "weather API endpoint", "limit": 3}'
