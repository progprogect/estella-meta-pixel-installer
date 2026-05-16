# Примеры концептов Extella

Концепты — это **техническое знание** в PostgreSQL + pgvector.
Ищутся семантически через concept_search(query).
НЕ содержат: ключи API, токены, пути пользователя, личные данные.

---

## Тип 1: Решение ошибки (паттерн: проблема → причина → решение)

```text
PDF text extraction — пустой результат со сканами

ПРОБЛЕМА: PyPDF2 / pdfplumber возвращают пустую строку для
сканированных PDF (image-based).

ПРИЧИНА: Сканированный PDF содержит только растровые изображения,
текстового слоя нет — парсеру просто нечего читать.

РЕШЕНИЕ: Использовать OCR-pipeline:
  1. pdf2image.convert_from_path() → список PIL Images
  2. pytesseract.image_to_string(image) → текст

УСТАНОВКА: extella-pip install pytesseract pdf2image

СИСТЕМНАЯ ЗАВИСИМОСТЬ: Tesseract OCR должен быть установлен
  macOS: brew install tesseract
  Ubuntu: apt-get install tesseract-ocr

АЛЬТЕРНАТИВА: Google Vision API — точнее, но платно.
КОГДА ПРИМЕНЯТЬ: когда PyPDF2 возвращает "" или text = "".
Тип 2: Паттерн работы с API (что использовать, как передавать ключи)OpenAI API — правильный паттерн вызова из эксперта

BASE URL: https://api.openai.com/v1/chat/completions

ВАЖНО: ключ НИКОГДА не хранится в коде или kwargs.
Агент получает ключ из KV Store и инжектирует через параметр.

ПАТТЕРН ПАРАМЕТРА:
  api_key: str = ""  # агент передаёт значение при запуске

ПАТТЕРН ВЫЗОВА:
  headers = {"Authorization": f"Bearer {api_key}"}
  payload = {
      "model": "gpt-4o-mini",
      "messages": [{"role": "user", "content": prompt}],
      "temperature": 0.7
  }

ОГРАНИЧЕНИЯ:
  - Rate limit: 429 Too Many Requests → ждать retry_after секунд
  - Max context: gpt-4o = 128K tokens, gpt-4o-mini = 128K tokens
  - Streaming: возможен, но эксперты возвращают синхронный результат

KV KEY: ключ обычно хранится как 'openai_api_key'
Тип 3: Best practice / предпочтение библиотекиГенерация PDF в Python — выбор библиотеки

РЕКОМЕНДУЕТСЯ: ReportLab
  - Pure Python, zero системных зависимостей
  - Работает на macOS/Windows/Linux из коробки
  - extella-pip install reportlab

НЕ РЕКОМЕНДУЕТСЯ: pdfkit
  - Требует wkhtmltopdf — системная бинарная зависимость
  - Ломается если wkhtmltopdf не установлен
  - Сложная отладка на CI/CD

НЕ РЕКОМЕНДУЕТСЯ ДЛЯ СОЗДАНИЯ: PyPDF2 / pypdf
  - Только для чтения и манипуляции существующими PDF
  - Не предназначены для создания с нуля

АЛЬТЕРНАТИВА: fpdf2 (лёгче ReportLab, подходит для простых документов)
  extella-pip install fpdf2
Тип 4: Маппинг ключей в KV Store (БЕЗ самих значений!)API Keys Mapping — пользователь john_a1b2c3d4

Ключи хранятся в KV Store (значения зашифрованы):
  OpenAI API key  → KV key: 'openai_api_key'
  Telegram token  → KV key: 'telegram_bot_token'
  Telegram chat   → KV key: 'telegram_chat_id'
  Replicate token → KV key: 'replicate_api_token'
  Groq API key    → KV key: 'groq_api_key'

ПРИНЦИП: Концепт хранит ИМЕНА ключей, не значения.
Значения — только в KV Store с шифрованием.
Тип 5: Ограничение сервиса / workaroundTelegram Bot API — ограничения на размер файлов

ЛИМИТЫ:
  sendPhoto:    ≤ 10 MB
  sendDocument: ≤ 50 MB
  sendVideo:    ≤ 50 MB
  sendVoice:    ≤ 1 MB (OGG/OPUS)

ПРИ ПРЕВЫШЕНИИ:
  - Файлы до 50MB → sendDocument (универсально)
  - Файлы > 50MB → загрузить на внешний хостинг (S3, GDrive),
    отправить ссылку через sendMessage

RATE LIMITS:
  - 30 сообщений/сек общий лимит бота
  - 1 сообщение/сек в один чат
  - На 429 Too Many Requests: смотреть поле retry_after в ответе
Что НЕ хранить в концептах❌ "OpenAI key: sk-abc123..."          → только в KV Store
❌ "Target ID: 83392960-e037-..."      → только в Targets DB  
❌ "Отправлять на john@company.com"    → личные данные
❌ "Webhook: https://hooks.slack.com/services/T.../B..."
❌ "Бот токен: 7654321:AABBcc..."
Как добавить концепт через APIPOST https://api.extella.ai/api/concept/add
Headers: X-Auth-Token: <your_token>
Body:
{
  "text": "PDF text extraction — пустой результат..."
}

# Ответ:
{
  "status": "success",
  "id": 42,
  "text": "PDF text extraction — пустой результат..."
}
