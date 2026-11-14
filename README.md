# ChatSCD

ChatSCD is a Scottish Country Dance assistant with a FastAPI web interface,
using the SCDDB dance catalogue and RSCDS teaching resources.

## Three parts

- **Chat** — ask about dances, search the catalogue and look up teaching guidance.
- **Lesson planner** — build class plans with full cribs and RSCDS manual teaching points.
- **Programme planner** — generate, edit and check dance programmes against chosen rules;
  generation and checking use the local catalogue, without model or network requests.

## Run locally

Use Python 3.12+ and `uv`, from the repository root. Supply the existing dance
catalogue at `data/scddb/scddb.sqlite` (or set `SCDDB_SQLITE` to its path).
Teaching lookups use `data/manual/` and `data/teaching_guide/teaching_guide.json`.
These data files are not checked in.

```sh
uv sync
./start_local_planner.sh
```

Open http://127.0.0.1:8015 and use the Chat, Lesson planner and Programme planner tabs
(the programme page is http://127.0.0.1:8015/programmes).
The launcher binds to loopback and uses separate chat/settings databases under
`data/local-preview/`; set `CHAT_SCD_LOCAL_PORT` to change the port.
Chat and lesson planning need a configured model provider/API key (OpenAI by default);
see [web app configuration](WEB_APP_README.md#environment-variables).
Programme generation/checking do not need a key. Lesson plans use `data/lesson_plans.db`.

## Tests without network or models

With dependencies installed and the catalogue at `data/scddb/scddb.sqlite`, run
these focused regressions from the repository root. They use local data and
in-process HTTP tests, not a running server or model API:

```sh
CHAT_DB_PATH=data/local-preview/tests-chat.db \
SETTINGS_DB_PATH=data/local-preview/tests-settings.db \
.venv/bin/python -m unittest \
  test_programme_planner test_dance_difficulty test_name_search \
  test_search_cribs_rscds test_feedback test_usage_quota -q
```

Use a disposable local checkout/data directory: importing lesson tools creates
`data/lesson_plans.db`. Do not run all `test_*.py` indiscriminately: some call models
or a live server; the legacy chat persistence/session scripts delete their configured DB.

## Documentation

- [Programme planner: local preview, rules and validation](docs/programme-planner.md)
- [Difficulty grades and nightly catalogue refresh](docs/difficulty-and-refresh.md)
- [Database fields enhancement roadmap](docs/database_fields_roadmap.md)
- [Data sources, UX roadmap and sustainability](docs/growth-and-sustainability.md)
