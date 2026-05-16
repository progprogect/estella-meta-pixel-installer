# Концепты и Rules — CSPL система extella
**Создано:** Апрель 2026 | **Платформа:** extella

---

## КОНЦЕПТЫ

---

### concept_id: 76809
## nohup CSPL — встроенный CSPL для фонового запуска

`cspl="nohup"` — встроенный CSPL extella. Эксперт с этим cspl запускается как **detached subprocess** через `subprocess.Popen + os.setsid` и немедленно возвращает управление.

### Как работает handler
Тело эксперта (Python-скрипт или {{placeholders}})
↓
extella Listener
↓  cspl = "nohup"
nohup CSPL Handler (containers_folder/nohup)
↓
Подстановка {{placeholders}} из kwargs
Если kwargs["file_path"] → запускает существующий файл
Иначе → пишет код во /tmp/nohup_{func_name}_{uuid}.py
subprocess.Popen([python, script], preexec_fn=os.setsid)
Пишет PID в /tmp/nohup_{func_name}.pid
return {pid, log_file, pid_file, script_file} — СРАЗУ

### Файлы
| Файл | Назначение |
|---|---|
| `/tmp/nohup_{func_name}.log` | stdout + stderr процесса |
| `/tmp/nohup_{func_name}.pid` | PID процесса |
| `/tmp/nohup_{func_name}_*.py` | Сгенерированный runner-скрипт |

### Возвращает
```python
{
    "status": "success",
    "pid": 38201,
    "log_file": "/tmp/nohup_task_registry_server.log",
    "pid_file": "/tmp/nohup_task_registry_server.pid",
    "script_file": "/tmp/nohup_task_registry_server.py",
    "func_name": "task_registry_server"
}
Поддержка {{placeholders}}# Тело эксперта с cspl=nohup:
PORT = {{port}}
HOST = "{{host}}"

import http.server
server = http.server.HTTPServer((HOST, PORT), http.server.BaseHTTPRequestHandler)
server.serve_forever()
Установкаrun_expert('create_nohup_cspl_container')
# Устанавливает handler в containers_folder/nohup
Ограничения vs parallel_task CSPLКритерийnohup CSPLparallel_task CSPLИдентификаторPID (переиспользуется ОС)UUID (уникален навсегда)Трекинг статусаНетTask RegistrySilent crashЗадача зависает в "running"Всегда пишет error в RegistryCancelkill PID вручнуюКнопка в UIРезультатВ log-файлеВ Registry → JSONPersistent stateНет/tmp/extella_task_registry.jsonFlowchartНетАвто PNG через code_to_flowchartВывод: nohup CSPL — низкоуровневый примитив. parallel_task CSPL строится поверх той же идеи, добавляя UUID-трекинг, Registry и UI.concept_id: 76811parallel_task CSPL как nested_expert — паттерн оркестрацииНестед-эксперт с cspl=fython оркестрирует параллельные задачи, запуская воркеры с cspl=parallel_task через REST API extella. Позволяет LLM описать сложный workflow один раз в коде, а не управлять им пошагово в reasoning.АрхитектураАгент
  ↓ run_expert('my_pipeline', {...})
  ↓
Nested Expert (cspl=fython)
  ├── run /api/expert/run → worker_A (cspl=parallel_task) → uuid_A
  ├── run /api/expert/run → worker_B (cspl=parallel_task) → uuid_B
  ├── run /api/expert/run → worker_C (cspl=parallel_task) → uuid_C
  │
  └── run /api/expert/run → demo_wait_tasks → {results: {uuid_A, uuid_B, uuid_C}}
        ↓
      return агрегированный результат
Шаблон кода nested_expert$extens("include.py")
include("import requests", ["extella-pip install requests"])

def my_parallel_pipeline(
    api_token_key: str = "extella_api_token",
) -> dict:
    import os, json, requests

    base_url = os.environ.get("EXTELLA_API_URL", "https://api.extella.ai")

    # 1. Получить API token
    tok = requests.post(base_url + "/api/kv/get",
        headers={"X-Auth-Token": api_token_key},
        json={"key": api_token_key}, timeout=10)
    API_TOKEN = tok.json()["value"]
    hdrs = {"X-Auth-Token": API_TOKEN, "Content-Type": "application/json"}

    def run(expert_name, params):
        params["__api_token__"] = API_TOKEN
        r = requests.post(base_url + "/api/expert/run",
            headers=hdrs,
            json={"expert_name": expert_name, "params": params},
            timeout=30)
        return r.json()["result"]

    # 2. Убедиться что Registry запущен
    run("task_registry_server", {})

    # 3. Fan-out — запустить параллельно (все возвращают СРАЗУ)
    r1 = run("worker_A", {"param": "value_a", "__description__": "Task A"})
    r2 = run("worker_B", {"param": "value_b", "__description__": "Task B"})
    r3 = run("worker_C", {"param": "value_c", "__description__": "Task C"})

    # 4. Barrier — дождаться всех
    results = run("demo_wait_tasks", {
        "uuids": json.dumps([r1["uuid"], r2["uuid"], r3["uuid"]]),
        "timeout": 300,
        "poll_interval": 2
    })

    # 5. Агрегировать и вернуть
    if results["status"] != "complete":
        return {"status": "partial_failure", "summary": results["summary"]}

    return {
        "status": "success",
        "results": {uuid: t["result"] for uuid, t in results["results"].items()},
        "elapsed_seconds": results["elapsed_seconds"],
        "summary": results["summary"]
    }
Паттерны оркестрации в nested_expertFan-out / Fan-in:uuids = []
for item in items:
    r = run('worker', {'data': item})
    uuids.append(r['uuid'])
results = run('demo_wait_tasks', {'uuids': json.dumps(uuids)})
Conditional routing:check = run('check_condition', {'input': data})
if check['result']['is_valid']:
    r = run('process_valid', {'data': data})
else:
    r = run('handle_invalid', {'data': data})
Retry on error:for attempt in range(3):
    r = run('unstable_worker', {'data': data})
    result = run('demo_wait_tasks', {'uuids': json.dumps([r['uuid']]), 'timeout': 60})
    if result['summary']['complete'] == 1:
        break
    time.sleep(5)
Sequential pipeline (A → B → C с передачей данных):r_a = run('fetch_data', {'url': url})
wait_a = run('demo_wait_tasks', {'uuids': json.dumps([r_a['uuid']])})
data = wait_a['results'][r_a['uuid']]['result']['data']

r_b = run('process_data', {'data': data})
wait_b = run('demo_wait_tasks', {'uuids': json.dumps([r_b['uuid']])})
Критические правила
Nested expert получает API token через KV Store (kv_get('extella_api_token'))
Все воркеры должны иметь cspl=parallel_task
__api_token__ передаётся в каждый run() вызов для генерации flowchart
task_registry_server ДОЛЖЕН быть запущен до воркеров
Результаты доступны через results['results'][uuid]['result']
demo_wait_tasks — единственный эксперт с cspl=wait_tasks, используется как barrier
concept_id: 27325Параллельный запуск задач — parallel_task CSPL + wait_tasks CSPLШаг 0. Убедиться что Registry запущенrun_expert('task_registry_server')
# → {status: 'already_running'|'started', ui: 'http://localhost:7755/'}
UI на http://localhost:7755/ — задачи, Cancel, 📊 flowchart.Шаг 1. Эксперт с cspl=parallel_taskЛюбой эксперт с cspl='parallel_task' запускается как nohup-subprocess и немедленно возвращает UUID.Специальные kwargs (pop-аются до вызова функции):
__registry_url__ — URL registry (default http://localhost:7755)
__description__ — описание задачи для UI
__api_token__ — extella API token → автогенерирует PNG flowchart
Шаг 2. Запустить несколько задач параллельноr1 = run_expert('my_worker', {'param': 'hello', '__api_token__': API_TOKEN})
r2 = run_expert('my_worker', {'param': 'world', '__api_token__': API_TOKEN})
r3 = run_expert('other_worker', {'x': 42,       '__api_token__': API_TOKEN})

uuid1 = r1['uuid']
uuid2 = r2['uuid']
uuid3 = r3['uuid']
Шаг 3. Дождаться завершения — demo_wait_tasks (cspl=wait_tasks)results = run_expert('demo_wait_tasks', {
    'uuids': json.dumps([uuid1, uuid2, uuid3]),
    'timeout': 300,
    'poll_interval': 2
})
# results['status']  → 'complete' | 'partial_failure'
# results['summary'] → {total: 3, complete: 3, error: 0, timeout: 0}
# results['results'] → {uuid1: {status, result, error, ...}, ...}
Готовые экспертыЭкспертCSPLРольtask_registry_serverfythonFlask-демон :7755, JSON-персистентность, UI с Cancel + 📊demo_parallel_workerparallel_taskТест: sleep N сек, greetingprime_finder_workerparallel_taskРешето Эратосфена + классификацияtext_stats_workerparallel_taskАнализ текста: FK grade, частотностьdemo_wait_taskswait_tasksОжидание списка UUID с timeoutcode_to_flowchartfythonPNG блок-схема кода через GPT-4o + matplotlibКритические правила
task_registry_server ДОЛЖЕН быть запущен до parallel_task экспертов
UUID (не PID) — PID переиспользуется ОС
JSON-файл /tmp/extella_task_registry.json — стейт выживает при рестарте Flask
Wrapper ВСЕГДА вызывает /update (try/except на всё) → нет silent crash
__api_token__ = значение ключа extella_api_token из KV Store
uuids передавать как JSON-строку: json.dumps([uuid1, uuid2])
concept_id: 76828UI CSPL — паттерн создания интерфейсов через декларативный JSONUI CSPL = CSPL-обработчик, принимающий декларативное описание UI (JSON) и детерминированно генерирующий HTML, .tscn, PPTX, React, TUI, SVG. LLM описывает ЧТО — handler генерирует КАК.Готовые UI CSPL (Godot)CSPLВходВыходgodot_ui_sceneJSON дерево нод.tscn UI сценаgodot_level_2dJSON платформы/объекты.tscn полная сценаgodot_themeJSON стили контроловTheme.tresAnchor presets вместо пикселейUI CSPL принимает семантические позиции: full_rect, center, top_wide, bottom_wide, hcenter_wide, vcenter_wide. Handler вычисляет реальные координаты сам — LLM не занимается математикой пикселей.JSON-структура UI CSPL{
  "root_type": "Control",
  "full_rect": true,
  "script": "res://scripts/MainMenu.gd",
  "children": [
    {"type": "ColorRect", "name": "Background",
     "anchor": "full_rect",
     "properties": {"color": "Color(0.05,0.05,0.1,1)"}},
    {"type": "VBoxContainer", "name": "Buttons",
     "anchor": "center",
     "children": [
       {"type": "Button", "text": "Play"},
       {"type": "Button", "text": "Options"},
       {"type": "Button", "text": "Quit"}
     ]}
  ]
}
Примеры UI CSPL вне Godot
html_ui — JSON → single-file HTML + Tailwind
pptx_slide — JSON layout → python-pptx слайды
react_component — JSON props → .tsx компонент
textual_tui — JSON виджеты → Python Textual TUI
svg_diagram — JSON nodes/edges → .svg блок-схема
latex_doc — JSON sections → .tex документ
Когда создавать UI CSPL
Повторяющийся тип UI (много меню, много слайдов, много уровней)
Целевой формат имеет сложный синтаксис (.tscn, PPTX XML, HTML)
Нужна токен-экономия: JSON << Python-генератор << вся разметка
Создание через cspl_builder_codesave_expert(
    name='create_pptx_slide_cspl',
    cspl='cspl_builder_code',
    code='''
def pptx_slide(
    filtered_source_code='', func_name='', args=None, kwargs=None,
    cspl='pptx_slide', response_format=None, **extra):
    import json
    from pathlib import Path
    spec = json.loads(filtered_source_code)
    output_path = kwargs.get('output_path', f'/tmp/{func_name}.pptx')
    # ... детерминированная генерация PPTX ...
    return {"status": "success", "path": output_path}
'''
)
concept_id: 76830Модульная разработка через вложенные CSPL — Atomic ArchitectureКонцепция: всё до атомаМодульный CSPL = CSPL-обработчик, тело которого вызывает другие эксперты через REST API. Позволяет строить иерархию от атома до архитектуры:Атомарный уровень (CSPL #0 — примитивы):
  html_button  → <button class="...">{{text}}</button>
  html_input   → <input type="{{type}}" placeholder="{{ph}}">
  css_var      → --{{name}}: {{value}};

Компонентный уровень (CSPL #1 — из атомов):
  html_form    → вызывает html_button × N + html_input × N
  nav_bar      → вызывает html_button × N + css_module
  html_card    → вызывает атомы + layout

Модульный уровень (CSPL #2 — из компонентов):
  auth_page    → вызывает html_form + nav_bar
  dashboard    → вызывает html_card × N + nav_bar

Системный уровень (CSPL #3 — из модулей):
  web_app      → вызывает auth_page + dashboard + API-роуты

Архитектурный уровень (CSPL #4 — из систем):
  saas_platform → вызывает web_app + admin_panel + api_gateway
Паттерн вызова sub-experts в CSPL handlerdef html_page(filtered_source_code='', func_name='', kwargs=None, **extra):
    import json, requests, os
    spec = json.loads(filtered_source_code)
    base_url = os.environ.get('EXTELLA_API_URL', 'https://api.extella.ai')
    token = (kwargs or {}).get('api_token', '')
    hdrs = {'X-Auth-Token': token, 'Content-Type': 'application/json'}

    def call(expert_name, params):
        r = requests.post(base_url + '/api/expert/run',
            headers=hdrs, json={'expert_name': expert_name, 'params': params}, timeout=30)
        return r.json()['result']['html']

    nav    = call('html_navbar',       {'items': spec['nav_items']})
    hero   = call('html_hero_section', {'title': spec['title'], 'cta': spec['cta']})
    cards  = [call('html_card', c) for c in spec['cards']]
    footer = call('html_footer',       {'links': spec['footer_links']})

    page = "<!DOCTYPE html>\n<html>\n" + nav + hero + ''.join(cards) + footer + "\n</html>"
    from pathlib import Path
    Path((kwargs or {}).get('output_path', '/tmp/page.html')).write_text(page)
    return {'status': 'success'}
Применение: сверхмодульный сайтJSON спецификация (100 токенов) → create_site CSPL
  → create_page × 4
    → create_navbar + create_hero + create_features + create_footer
      → create_button + create_card + create_input × N
→ Готовый статик-сайт 4 HTML + CSS + JS (0 токенов на вёрстку)
Применение: архитектура процессораJSON: {name: "MinRISC-1", isa: "RISC-V RV32I", pipeline: [...], registers: 32}
→ create_cpu_verilog CSPL
  → create_alu_module          → alu.v
  → create_register_file       → regfile.v
  → create_pipeline_stage × 5  → if_stage.v, id_stage.v...
  → create_memory_controller   → mem_ctrl.v
  → create_testbench           → cpu_tb.v
→ Полный Verilog проект (симулируется в Icarus Verilog)
Правила модульной декомпозиции
Атом = один файл или один компонент (не делится далее)
Каждый уровень вызывает только уровень ниже (не перепрыгивает)
Интерфейс между уровнями = JSON-спецификация
Handler каждого уровня — детерминированный Python
LLM работает только с верхним JSON — не видит внутренности
concept_id: 76831Кастомные языки программирования через CSPL (Domain-Specific Languages)Зачем создавать DSL через CSPL
Экономия токенов: DSL компактнее Python/JSON в 5–20 раз
Точность: LLM пишет на простом языке → меньше галлюцинаций
Специализация: синтаксис отражает предметную область
Детерминированность: парсер в handler — не LLM
АрхитектураТело эксперта = код на DSL
         ↓
   extella Listener  (cspl = "my_dsl")
         ↓
   DSL Handler (Python парсер + кодогенератор)
         ↓
   Целевой артефакт (Python, SQL, Verilog, HTML, GDScript)
Пример: DSL для Web APIAPI UserService
  BASE /api/users
  AUTH bearer

  GET  /      -> list[User]  CACHE 60
  POST /      -> User        BODY {name: str, email: str}
  GET  /:id   -> User
  PUT  /:id   -> User
  DELETE /:id -> void        CONFIRM "Delete user?"

→ Handler генерирует: FastAPI router + Pydantic схемы + OpenAPI + SDK
Пример: DSL для игровой логикиENTITY Player
  HEALTH 100 MAX 100
  SPEED 200
  JUMP_FORCE 500

  ON touch Spike:
    DEAL_DAMAGE 20
    FLASH_RED 0.3
    IF HEALTH <= 0: GOTO GameOver

  ON touch Key:
    SET has_key = true
    PLAY sound_pickup
    DESTROY self

→ Handler генерирует GDScript Player.gd (200 строк из 15 строк DSL)
Пример: HDL DSL для микросхемMODULE alu_4bit
  INPUT  a[4], b[4], op[2]
  OUTPUT result[4], zero, overflow

  WHEN op == 00: result = a + b
  WHEN op == 01: result = a - b
  WHEN op == 10: result = a AND b
  WHEN op == 11: result = a OR b
  zero     = (result == 0)
  overflow = carry_out XOR carry_in

→ Handler генерирует Verilog alu_4bit.v + testbench
Создание DSL CSPL через cspl_builder_codedef my_api_dsl(
    filtered_source_code='', func_name='', args=None, kwargs=None,
    cspl='my_api_dsl', response_format=None, **extra):

    def parse_dsl(src):
        ast = {'name': '', 'base': '', 'routes': [], 'auth': ''}
        for line in src.splitlines():
            line = line.strip()
            if line.startswith('API '): ast['name'] = line[4:]
            elif line.startswith('BASE '): ast['base'] = line[5:]
            elif line.startswith(('GET','POST','PUT','DELETE')):
                parts = line.split()
                ast['routes'].append({'method': parts[0], 'path': parts[1]})
        return ast

    def generate_fastapi(ast):
        lines = [f"# Auto-generated: {ast['name']}", "from fastapi import APIRouter",
                 "router = APIRouter()", ""]
        for r in ast['routes']:
            lines.append(f"@router.{r['method'].lower()}('{r['path']}')")
            lines.append(f"async def handler_{r['method']}_{r['path'].strip('/')
                .replace('/','_')}(): pass")
        return '\n'.join(lines)

    ast  = parse_dsl(filtered_source_code)
    code = generate_fastapi(ast)
    from pathlib import Path
    out = Path((kwargs or {}).get('output_path', f'/tmp/{func_name}.py'))
    out.write_text(code)
    return {'status': 'success', 'path': str(out), 'routes': len(ast['routes'])}
Матрица применения DSL CSPLДоменDSL CSPLГенерируетЭкономия токеновWeb APIapi_dslFastAPI + schemas10×Игровая логикаgame_logic_dslGDScript / Lua15×База данныхschema_dslSQL DDL + migrations8×CI/CDpipeline_dslGitHub Actions YAML12×Микросхемыhdl_dslVerilog / VHDL20×Конфигурацияconfig_dslJSON/YAML/TOML5×Тестыtest_dslpytest fixtures6×concept_id: 76832CLI CSPL — работа с командной строкой для экономии токеновПринцип: CLI как интерфейс агента
Компактный ввод/вывод: grep -r 'pattern' /dir вместо 500-строчного Python
Композируемость: pipe (|) цепочки без кода
Детерминированность: CLI-команды предсказуемы
Экономия токенов: команда = 1–2 строки, Python-скрипт = 50–200 строк
Встроенный shell CSPL# Тело эксперта с cspl=shell:
find {{dir}} -name '*.py' | xargs grep -l '{{pattern}}' | head -20
Кастомный CLI CSPLdef ffmpeg_cli(
    filtered_source_code='', func_name='', kwargs=None, **extra):
    import subprocess, shlex
    cmd = filtered_source_code
    for k, v in (kwargs or {}).items():
        cmd = cmd.replace('{{'+k+'}}', str(v))
    r = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=120)
    return {'stdout': r.stdout, 'stderr': r.stderr, 'returncode': r.returncode}
Примеры CLI CSPL экспертов# cli_git
save_expert(name='git_release', cspl='cli_git', code='''
git add -A
git commit -m "{{message}}"
git tag v{{version}}
git push origin main --tags
''')

# cli_docker
save_expert(name='deploy_service', cspl='cli_docker', code='''
docker build -t {{image}}:{{tag}} .
docker push {{image}}:{{tag}}
docker service update --image {{image}}:{{tag}} {{service_name}}
''')

# cli_ffmpeg
save_expert(name='convert_video', cspl='cli_ffmpeg', code='''
ffmpeg -i {{input}} -vf scale={{width}}:-1 -crf {{quality}} -preset fast {{output}}
''')

# cli_ssh
save_expert(name='deploy_to_server', cspl='cli_ssh', code='''
ssh {{host}} 'cd {{dir}} && git pull && systemctl restart {{service}}'
''')
Экономия токенов: CLI vs PythonЗадачаPython экспертCLI командаЭкономияНайти файлы по паттерну20 строкfind . -name '*.py'95%Конвертировать видео50 строкffmpeg -i in out90%Деплой Docker30 строк3 команды85%Git операции25 строкgit add && commit90%SSH команды15 строкssh host 'cmd'80%Критические правила
Всегда timeout — CLI может зависнуть
capture_output=True — получаем stdout/stderr
check=False — не поднимать исключение на non-zero exit
Возвращать returncode + stderr для диагностики
shlex.split() для безопасного разбора команд
Никогда shell=True с пользовательскими данными — инъекции
concept_id: 76833Подключение интерпретаторов и компиляторов через CSPLКонцепция: polyglot CSPLCSPL оборачивает ЛЮБОЙ внешний интерпретатор в эксперт extella. Тело эксперта пишется на целевом языке, handler компилирует/запускает и возвращает результат.АрхитектураТело эксперта = код на целевом языке (Ruby, Go, R, Lua, Verilog...)
         ↓  CSPL Handler
         ↓  subprocess.run([interpreter, script_file])
         ↓
   return {stdout, stderr, returncode, artifacts}
Готовые паттерныRuby:def ruby_exec(filtered_source_code='', func_name='', kwargs=None, **extra):
    import subprocess, tempfile
    with tempfile.NamedTemporaryFile(suffix='.rb', mode='w', delete=False) as f:
        f.write(filtered_source_code); tmp = f.name
    r = subprocess.run(['ruby', tmp], capture_output=True, text=True, timeout=30)
    return {'stdout': r.stdout, 'stderr': r.stderr, 'exit': r.returncode}
Go (компилятор):def go_run(filtered_source_code='', func_name='', kwargs=None, **extra):
    import subprocess, tempfile
    from pathlib import Path
    tmp_dir = Path(tempfile.mkdtemp())
    (tmp_dir / 'main.go').write_text(filtered_source_code)
    r = subprocess.run(['go', 'run', str(tmp_dir / 'main.go')],
        capture_output=True, text=True, timeout=60, cwd=str(tmp_dir))
    return {'stdout': r.stdout, 'stderr': r.stderr, 'exit': r.returncode}
Verilog (Icarus):def verilog_sim(filtered_source_code='', func_name='', kwargs=None, **extra):
    import subprocess, tempfile
    from pathlib import Path
    tmp = Path(tempfile.mkdtemp())
    src = tmp / f'{func_name}.v'
    src.write_text(filtered_source_code)
    comp = subprocess.run(['iverilog', '-o', str(tmp/'sim'), str(src)], capture_output=True, text=True)
    if comp.returncode != 0:
        return {'status': 'error', 'compile_error': comp.stderr}
    sim = subprocess.run([str(tmp/'sim')], capture_output=True, text=True, timeout=10)
    return {'status': 'success', 'simulation': sim.stdout}
SQLite (встроенный):def sqlite_exec(filtered_source_code='', func_name='', kwargs=None, **extra):
    import sqlite3
    db_path = (kwargs or {}).get('db_path', ':memory:')
    conn = sqlite3.connect(db_path)
    results = []
    for stmt in filtered_source_code.split(';'):
        stmt = stmt.strip()
        if not stmt: continue
        cur = conn.execute(stmt)
        if cur.description:
            cols = [d[0] for d in cur.description]
            results.append({'cols': cols, 'rows': cur.fetchall()})
    conn.commit()
    return {'status': 'success', 'results': results}
Таблица интерпретаторовCSPLИнтерпретаторУстановкаПрименениеruby_execrubybrew install rubyСкриптингgo_rungobrew install goСистемное ПОrust_runrustccurl rustup.rsСистемное ПОjulia_execjuliabrew install juliaВычисленияr_execRscriptbrew install rСтатистикаlua_execluabrew install luaВстроенный скриптингverilog_simiverilogbrew install icarus-verilogСимуляция схемsqlite_execsqlite3stdlibЛокальные БДnode_execnodebrew install nodeJS/TSdeno_execdenobrew install denoTS безопасныйwasm_execwasmtimebrew install wasmtimeWebAssemblyzig_execzigbrew install zigСистемное ПОPolyglot pipeline (nested expert)def polyglot_pipeline(data_path, api_token):
    stats  = call('r_stats_expert',  {'data': data_path})            # R
    model  = call('python_ml_train', {'data': data_path,             # Python
                                      'features': stats['features']})
    chart  = call('node_d3_chart',   {'output': model['predictions']})# Node.js
    report = call('latex_report',    {'stats': stats, 'chart': chart})# LaTeX
    return {'pdf': report['path']}
concept_id: 76834Agents API extella — полная спецификация (апрель 2026)Base URL: https://api.extella.aiАутентификация
X-Auth-Token: <token> в каждом запросе
POST /api/token/validate → {valid: bool, user_id: str}
Чужой agent_id/profile_id → 403 Forbidden
Все 11 endpointsAGENTS#МетодПутьНазначение1POST/api/agent/runОтправить сообщение агенту2GET/api/agent/getКонфигурация (без credentials)3POST/api/agent/createСоздать агента → agent_id4POST/api/agent/updatePartial update (model, prompt, experts)5POST/api/agent/deleteУдалить агента (memory НЕ удаляется)6POST/api/agent/listВсе агенты (фильтр по profile_id)PROFILES#МетодПутьНазначение7POST/api/profile/createГруппа агентов с общими экспертами8POST/api/profile/add_agentДобавить агента в профиль9POST/api/profile/deleteУдалить профиль (агенты живут)EXPORT#МетодПутьНазначение10POST/api/agent/export/chatsИстория чатов (для Sleep/fine-tuning)11POST/api/agent/export/callsЛог API-вызовов (для RL Router)/api/agent/run — режимы# sync (default) — блокирующий
resp = requests.post(base_url + '/api/agent/run',
    headers={'X-Auth-Token': token, 'X-Agent-Id': agent_id, 'X-Profile-Id': profile_id},
    json={'message': 'Analyze: ...'})
answer = resp.json()['answer']

# stream — SSE, токен за токеном
json={'message': '...', 'stream': True}

# async — немедленно возвращает task_id
resp = requests.post(..., json={'message': '...', 'async': True})
task_id = resp.json()['task_id']
# → poll GET /api/task/check?task_id=...
Разница: Агент vs ЭкспертАгентЭкспертИмеет LLMДаНетИмеет памятьДа (concepts/KV)НетВызовPOST /api/agent/runPOST /api/expert/runРезультатТекст/действиеdictСтоимостьДорого (LLM tokens)Дёшево (код)Когда использоватьСложные решения, reasoningПовторяемые операцииСпециализированные агенты
agent_sshOMcVZC_O4mBIfl9-Ym — кодинг-агент
agent_ymcL79rf_-qiqZXawsdDX — Grok творческий агент
Base URL: https://test.extella.ai
API ключ: KV key extella_test_agents_api_key
RULESrule_id: 6205Параллельный запуск задач (parallel_task CSPL)Если пользователь просит запустить несколько задач параллельно — использовать концепт 27325.
Алгоритм:
run_expert('task_registry_server') — убедиться что Registry запущен
Для каждого эксперта — cspl='parallel_task', запустить run_expert с __api_token__ = значение ключа extella_api_token из KV
Собрать UUID из результатов
Дождаться через run_expert('demo_wait_tasks', {uuids: json.dumps([...])})
Вернуть результаты пользователю
UI доступен на http://localhost:7755/rule_id: 8109UI → UI CSPL паттернДля создания UI (презентации, игровые сцены, веб-страницы, TUI) — использовать UI CSPL паттерн (concept_id 76828):
тело эксперта = JSON-описание UI
handler = детерминированный генератор
Готовые: godot_ui_scene, godot_level_2d, godot_theme.
Для новых UI — создавать через cspl_builder_code.rule_id: 8110Сложные системы → Atomic Architecture CSPLДля модульной разработки сложных систем (сайты, процессоры, компиляторы, игры) — применять Atomic Architecture CSPL (concept_id 76830):
Декомпозировать до атома
Каждый уровень вызывает только уровень ниже через REST API
Интерфейс между уровнями = JSON
LLM описывает только верхний уровень.rule_id: 8111Повторяемые задачи → DSL CSPLДля повторяющихся задач с высокой токенной стоимостью — создавать Domain-Specific Language (DSL) через CSPL (concept_id 76831).DSL компактнее Python в 5–20 раз, парсер в handler детерминирован.Примеры: api_dsl → FastAPI, game_logic_dsl → GDScript, hdl_dsl → Verilog, schema_dsl → SQL DDL.rule_id: 8112Shell-операции → CLI CSPLДля shell-операций (git, docker, ffmpeg, ssh, find, grep) — использовать CLI CSPL (concept_id 76832) вместо Python-скрипта: экономия 80–95% токенов.Тело эксперта = команды с {{placeholders}}, cspl=shell или кастомный cli_* CSPL.Правила: timeout, capture_output=True, shlex.split(), никогда shell=True с данными пользователя.rule_id: 8113Нестандартные языки → interpreter CSPLДля задач на нестандартных языках (Ruby, Go, R, Julia, Lua, Verilog, SQL, Node.js) — использовать interpreter CSPL (concept_id 76833).Тело эксперта пишется на целевом языке, handler запускает через subprocess.run([interpreter, tmp_file]).Для полиглот-пайплайнов — nested expert вызывает разные языковые CSPL.Сводная таблицаКонцептыIDНазваниеКлючевая идея76809nohup CSPLФоновый запуск через subprocess.Popen + os.setsid76811parallel_task как nested_expertOrchestration паттерны: fan-out, retry, conditional27325parallel_task CSPL + wait_tasksПолный гайд: Registry → parallel → wait → результат76828UI CSPLJSON → HTML/.tscn/PPTX/React/TUI детерминированно76830Atomic ArchitectureИерархия от атома до платформы через вложенные CSPL76831DSL через CSPLКастомные языки: api_dsl, game_logic_dsl, hdl_dsl76832CLI CSPLShell-команды с {{placeholders}}, 80–95% экономия токенов76833Interpreter CSPLRuby/Go/R/Verilog/SQL через subprocess.run76834Agents API11 endpoints: agent/run, profile, exportRulesIDТриггерДействие6205Запустить несколько задач параллельноparallel_task CSPL паттерн8109Создать UI (игра, презентация, веб)UI CSPL (JSON → артефакт)8110Сложная модульная системаAtomic Architecture CSPL8111Повторяющаяся задача, много токеновDSL через CSPL8112git/docker/ffmpeg/ssh операцииCLI CSPL8113Ruby/Go/R/Verilog/SQL задачаInterpreter CSPLАпрель 2026 | extella platform