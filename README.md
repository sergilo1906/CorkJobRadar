# Cork Job Radar

A Python application for collecting and reviewing public job listings in Cork. It runs locally on Windows with a Streamlit interface, SQLite storage and a separate background worker.

The main problem is keeping track of listings across different sources without losing the original posting, the source or previous review decisions. The radar normalises vacancies, stores their history, supports filters and exports results to Excel, CSV, JSON and Markdown. Searches can be cancelled and resumed.

## Run it on Windows

Use Python 3.12. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m corkjobradar doctor
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Open http://127.0.0.1:8501. Load the source catalogue in the interface before starting a search on a fresh installation. The source definitions are in `config/sources.yaml`.

The interface and background worker are separate processes. The worker can continue independently of the browser tab.

## Implementation notes

`corkjobradar/` contains the source adapters, normalisation, database, scoring, verification, CLI and worker. The Streamlit entry point is `app.py`. The test suite can be run with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The application also includes an assisted application workflow and experimental form preparation. Live external submissions remain disabled and unverified; the project does not guarantee complete coverage of the Cork job market.

Local databases, CVs, credentials and private exports are not part of a fresh clone. Windows-specific data protection and the current project limitations are described in [publication notes](docs/GITHUB_PUBLICATION.md).

More detail: [sources](docs/SOURCES.md), [local runtime](docs/LOCAL_RUNTIME_WINDOWS.md), [test report](docs/TEST_REPORT.md), [application workflow](docs/AUTOAPPLY_OPERATIONS.md).
