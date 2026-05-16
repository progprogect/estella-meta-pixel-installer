# Обновление концептов в Extella

## MCP-инструмент

```python
concept_update(
    concept_id=42,          # int — ID концепта (из concept_list или concept_search)
    new_text="...",         # str — новый текст (полностью заменяет старый)
    api_key=None,           # str | None — ключ для генерации эмбеддинга (опционально)
    global=False            # bool — разрешить обновление концептов других агентов
)
REST API (для nested experts)POST https://api.extella.ai/api/concept/update
Обязательные заголовкиЗаголовокЗначениеX-Auth-Tokenваш токенContent-Typeapplication/jsonX-Profile-IddefaultX-Agent-Idagent_extella_defaultТело запроса{
  "concept_id": 42,
  "new_text": "Обновлённое содержимое концепта"
}
Успешный ответ{
  "status": "success",
  "id": 42,
  "text": "Обновлённое содержимое концепта"
}

⚠️ Обратите внимание: ответ возвращает поля id и text
(не concept_id и concept_text как в concept_search / concept_list)
Ключевые особенности
Полная замена: new_text полностью перезаписывает старый текст — частичного обновления нет
Эмбеддинг пересчитывается автоматически после обновления текста
Изоляция по агенту: по умолчанию можно обновлять только концепты текущего агента
global=True: позволяет обновлять концепты других агентов (использовать осторожно)
Типичный сценарий использования# 1. Найти концепт по смыслу
results = concept_search(query="паттерн генерации PDF", limit=5)
concept_id = results["results"][0]["concept_id"]

# 2. Обновить — дополнить знание
concept_update(
    concept_id=concept_id,
    new_text="""
    PDF generation in Python:
    - ReportLab — pure Python, no system deps, recommended
    - pdfkit — requires wkhtmltopdf system binary, avoid in Docker
    - fpdf2 — lightweight alternative for simple documents
    """
)

# 3. Ответ содержит поля: id, text (не concept_id / concept_text!)
Когда обновлять, а не создавать новый концептСитуацияДействиеНайдено похожее знание (similarity ≥ 0.55)concept_updateЗнание устарело / найден лучший способconcept_updateДобавить детали к существующему концептуconcept_updateПринципиально новая темаconcept_add