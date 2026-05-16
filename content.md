# 📦 Шаблоны Extella: Expert и Concept

---

## 🤖 EXPERT — типовой шаблон

### Структура при сохранении (save_expert)

| Поле          | Описание                                          |
|---------------|---------------------------------------------------|
| `name`        | snake_case уникальный идентификатор               |
| `description` | Что делает + все параметры (используется в поиске)|
| `code`        | Полный Python-код с директивами                   |
| `kwargs`      | Параметры с дефолтными значениями                 |

---

### Пример 1: Простой API-вызов

```python
$extens("include.py")
include("import requests", ["extella-pip install requests"])

def get_weather(
    city: str = "",
    api_key: str = "",          # инжектируется агентом из KV Store
    units: str = "metric"       # metric | imperial
) -> dict:
    import requests

    print("[1/3] 🔄 Подготовка запроса...")

    if not city:
        return {"status": "error", "message": "city is required"}
    if not api_key:
        return {"status": "error", "message": "api_key is required"}

    print("[2/3] 🌐 Запрос к API погоды...")

    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": api_key, "units": units},
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()

        print("[3/3] ✅ Готово.")

        return {
            "status": "success",
            "city": city,
            "temperature": data["main"]["temp"],
            "description": data["weather"][0]["description"]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
Kwargs при сохранении:{
  "city": "",
  "api_key": "",
  "units": "metric"
}
Description при сохранении:Gets current weather for a city via OpenWeatherMap API.
Parameters: city — city name to query; api_key — OpenWeatherMap API key (injected);
units — temperature units (metric/imperial, default: metric).
Пример 2: Работа с файлом$extens("include.py")
include("from pathlib import Path", [])
include("import json", [])

def read_json_file(
    file_path: str = "",
    encoding: str = "utf-8"
) -> dict:
    from pathlib import Path
    import json

    print("[1/3] 🔄 Чтение файла...")

    if not file_path:
        return {"status": "error", "message": "file_path is required"}

    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        return {"status": "error", "message": f"File not found: {path}"}

    print("[2/3] ⚙️ Парсинг JSON...")

    try:
        content = path.read_text(encoding=encoding)
        data = json.loads(content)

        print("[3/3] ✅ Готово.")

        return {
            "status": "success",
            "file_path": str(path),
            "data": data
        }
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Invalid JSON: {e}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
❌ Типичные ошибки эксперта# ❌ НЕТ $extens
def my_expert(): ...

# ❌ Захардкоженный chat_id
send_message(chat_id="123456789", ...)

# ❌ API ключ прямо в коде
api_key = "sk-abc123..."

# ❌ Личный путь
file = "/home/john/report.pdf"

# ❌ Бинарные данные в return
return {"image": base64.b64encode(img)}

# ❌ *args / **kwargs в сигнатуре
def expert(*args, **kwargs): ...
🧠 CONCEPT — типовой шаблонКонцепт — это техническое знание в базе данных.
Хранит: паттерны, решения ошибок, ограничения API, best practices.НЕ хранит: API ключи, токены, пути к файлам, личные данные.Структура концепта[ТЕМА / КАТЕГОРИЯ]

КОНТЕКСТ: что за задача / ситуация
РЕШЕНИЕ: как решили
БИБЛИОТЕКА/API: что использовали
ДЕТАЛИ: важные нюансы
ОГРАНИЧЕНИЯ: что нужно учесть
Пример 1: Решение ошибкиPDF text extraction — решение проблемы со сканами

ПРОБЛЕМА: PyPDF2 возвращает пустую строку для сканированных PDF (image-based).

ПРИЧИНА: Сканированный PDF содержит только изображения, текстового слоя нет.

РЕШЕНИЕ: Использовать pytesseract + pdf2image для OCR:
  1. pdf2image.convert_from_path() → список PIL Images
  2. pytesseract.image_to_string(image) → текст

УСТАНОВКА: extella-pip install pytesseract pdf2image
ЗАВИСИМОСТЬ: Tesseract OCR должен быть установлен в системе.

АЛЬТЕРНАТИВА: Google Vision API (точнее, но платно).

КОГДА ПРИМЕНЯТЬ: когда PyPDF2 / pdfplumber возвращают пустой результат.
Пример 2: Паттерн работы с APITelegram Bot API — отправка сообщений

BASE URL: https://api.telegram.org/bot{token}/sendMessage

ПАРАМЕТРЫ:
  - chat_id: ID чата или @username
  - text: текст (до 4096 символов)
  - parse_mode: "HTML" | "Markdown" | "MarkdownV2" | "" (plain)

ОГРАНИЧЕНИЯ:
  - Max 30 сообщений/сек общий лимит
  - Max 1 сообщение/сек в один чат
  - На ошибку 429 (Too Many Requests) ждать retry_after секунд

ЛУЧШИЙ ПАТТЕРН: parse_mode="HTML", теги <b>, <i>, <code>
ХРАНЕНИЕ ТОКЕНА: в KV Store как 'telegram_bot_token'
Пример 3: Best practice / предпочтениеГенерация PDF в Python

РЕКОМЕНДУЕТСЯ: ReportLab (pure Python, no system dependencies)
НЕ РЕКОМЕНДУЕТСЯ: pdfkit (требует wkhtmltopdf — системная зависимость)

ПРИЧИНА: ReportLab работает из коробки на macOS/Windows/Linux без
дополнительных установок. pdfkit ломается если wkhtmltopdf не установлен.

УСТАНОВКА: extella-pip install reportlab
❌ Что НЕ сохранять в концепт# ❌ API ключ
"OpenAI key: sk-abc123..."

# ❌ Target ID
"Target: 83392960-e037-4055-..."

# ❌ Личный email
"Отправлять на john@company.com"

# ❌ Webhook URL с токеном
"https://hooks.slack.com/services/T0.../..."
Вместо этого → сохранить значение в KV Store, а в концепт записать только имя ключа:"Telegram bot token хранится в KV Store как 'telegram_bot_token'"
🔑 Ключевое различиеExpertConceptЧто этоИсполняемый Python-кодТекстовое знание в БДДля чегоДелает работуПомнит как делатьХранитсяPostgreSQL (experts table)PostgreSQL (concepts table)Ищется черезsearch_blocks(query)concept_search(query)Создаётся черезsave_expert(...)concept_add(text)