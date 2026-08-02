# PDF Report Generator

A production-ready **FastAPI + Celery + PostgreSQL** microservice that generates PDF order-summary reports asynchronously, demonstrates SQL-level aggregation, and supports both on-demand and scheduled (Celery Beat) report generation.

> Built as a backend engineering workshop project demonstrating: background jobs, message brokers, SQL aggregation, artifact storage, and async job-status APIs.

---

## Architecture

```
                   ┌──── POST /api/v1/reports
                   │
Client ────────────┤
                   └──── GET  /api/v1/reports/{id}
                          │        (status + download URL)
                          ▼
                      FastAPI (port 8000)
                          │
                    PostgreSQL (reports + orders)
                          ▲
                          │
              ┌───────────┴───────────┐
              │                       │
        On-demand trigger        Celery Beat
        (POST /reports)          (01:00 UTC daily)
              │                       │
              └──────────┬────────────┘
                         ▼
                       Redis (broker)
                         │
                         ▼
                   Celery Worker
                         │
              ┌──────────┼──────────┐
              │          │          │
        SQL Aggregation  │    Status updates
        (COUNT/SUM/AVG)  │    (PENDING → PROCESSING
              │          │     → COMPLETED / FAILED)
              ▼          │
          ReportLab       │
          PDF Build       │
              │           │
              ▼           │
        Shared Volume ────┘
        (storage/reports/)
              │
              ▼
        FileResponse
        (download endpoint)
```

---

## Features

| Feature | Detail |
|---|---|
| **On-demand report generation** | `POST /api/v1/reports` → 202 Accepted |
| **Async background processing** | Celery worker consumes `reports` queue |
| **Job status polling** | `GET /api/v1/reports/{id}` |
| **PDF download** | `GET /api/v1/reports/{id}/download` |
| **SQL aggregation** | `COUNT`, `SUM`, `AVG`, `COUNT DISTINCT`, `GROUP BY` pushed to Postgres |
| **Retry logic** | Exponential backoff (10s → 20s → 40s), max 3 retries, transient vs non-retryable errors |
| **Scheduled reports** | Celery Beat fires at 01:00 UTC daily; reuses the same generation pipeline |
| **Shared artifact storage** | Named Docker volume shared between `api` and `worker` |
| **Database migrations** | Alembic versioned schema |

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.141, Pydantic v2, Uvicorn |
| Task queue | Celery 5.6, Redis 7.2 |
| Database | PostgreSQL 16, SQLAlchemy 2.0, Alembic |
| PDF generation | ReportLab 4.0 |
| Containerisation | Docker, Docker Compose |
| Testing | pytest, pytest-asyncio, SQLite in-memory (API/unit), Postgres (integration) |

---

## Project Structure

```
pdf-report-generator/
├── app/
│   ├── api/routes/
│   │   └── reports.py          # POST, GET status, GET download
│   ├── core/
│   │   ├── celery_app.py       # Celery instance + Beat schedule
│   │   └── config.py           # pydantic-settings config
│   ├── db/
│   │   ├── database.py         # SQLAlchemy engine + session
│   │   └── models/
│   │       ├── order.py        # Order table
│   │       └── report.py       # Report table + ReportStatus enum
│   ├── schemas/
│   │   └── report.py           # Pydantic v2 request/response schemas
│   ├── services/
│   │   ├── pdf_service.py      # ReportLab PDF builder
│   │   ├── report_service.py   # DB operations + SQL aggregation
│   │   └── storage_service.py  # File path management
│   ├── workers/
│   │   ├── report_tasks.py     # Celery task (with retry logic)
│   │   └── scheduled_tasks.py  # Celery Beat daily task
│   └── main.py                 # FastAPI app entry point
├── alembic/                    # Database migrations
├── scripts/
│   └── seed_data.py            # Sample order data
├── tests/
│   ├── api/                    # FastAPI route tests (SQLite in-memory)
│   ├── unit/                   # Pure unit tests (no DB)
│   └── integration/            # SQL aggregation tests (real Postgres)
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
└── requirements.txt
```

---

## Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### 1. Clone and configure

```bash
git clone https://github.com/Abhi-T-A/pdf-report-generator.git
cd pdf-report-generator
```

Create a `.env` file (the Docker Compose overrides DB/Redis URLs automatically):

```env
DATABASE_URL="postgresql://postgres:postgres@localhost/pdf_report_db"
```

### 2. Build and start all services

```bash
docker compose up --build
```

Five services will start:

```
✅ db       PostgreSQL 16 (port 5433)
✅ redis    Redis 7.2     (port 6380)
✅ api      FastAPI       (port 8000)
✅ worker   Celery worker
✅ beat     Celery Beat   (daily schedule)
```

### 3. Run database migrations

```bash
docker compose exec api alembic upgrade head
```

### 4. Seed sample data

```bash
docker compose exec api python -m scripts.seed_data
```

### 5. Generate a report

```bash
# Create a report
curl -X POST http://localhost:8000/api/v1/reports \
  -H "Content-Type: application/json" \
  -d '{"report_type": "order_summary", "start_date": "2026-07-01", "end_date": "2026-07-06"}'

# Response: { "id": "<uuid>", "status": "PENDING", ... }
```

### 6. Poll status

```bash
curl http://localhost:8000/api/v1/reports/<uuid>

# When complete: { "status": "COMPLETED", "download_url": "http://..." }
```

### 7. Download the PDF

```bash
curl -O http://localhost:8000/api/v1/reports/<uuid>/download
```

---

## API Reference

### `POST /api/v1/reports`

Create and queue a new report.

**Request body:**
```json
{
  "report_type": "order_summary",
  "start_date": "2026-07-01",
  "end_date": "2026-07-06"
}
```

**Response:** `202 Accepted`
```json
{
  "id": "96d261dd-ce4e-4a23-8055-8deacd492959",
  "report_type": "order_summary",
  "status": "PENDING",
  "start_date": "2026-07-01",
  "end_date": "2026-07-06",
  "created_at": "2026-08-02T09:25:38Z"
}
```

### `GET /api/v1/reports/{report_id}`

Poll report status. When `COMPLETED`, includes a `download_url`.

**Response statuses:** `PENDING` → `PROCESSING` → `COMPLETED` | `FAILED`

### `GET /api/v1/reports/{report_id}/download`

Download the generated PDF. Returns `400` if not yet `COMPLETED`.

### `GET /health`

```json
{ "status": "healthy", "service": "pdf-report-generator" }
```

---

## Running Tests

```bash
# Install dependencies in a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Run API + unit tests (no database required)
pytest tests/api/ tests/unit/ -v

# Run integration tests (requires Postgres)
# Add TEST_DATABASE_URL to .env first:
# TEST_DATABASE_URL=postgresql://postgres:postgres@localhost/pdf_report_generator_test
pytest tests/integration/ -v

# Run all tests
pytest tests/ -v
```

### Test structure

| Suite | DB Required | What it tests |
|---|---|---|
| `tests/api/` | ❌ SQLite in-memory | FastAPI routes, request validation, status codes |
| `tests/unit/` | ❌ None | PDF generation, storage path logic |
| `tests/integration/` | ✅ Postgres | SQL aggregation (`COUNT/SUM/GROUP BY`), status transitions |

---

## Celery Beat — Scheduled Reports

The `beat` service fires `generate_daily_report` every day at **01:00 UTC**.

The scheduled task:
1. Determines yesterday's date range
2. Creates a `Report` row (status: `PENDING`)
3. Dispatches `generate_report_task.delay(report.id)` — the **same pipeline** as on-demand requests

```
Celery Beat ──► generate_daily_report ──► generate_report_task ──► PDF
API (POST) ──────────────────────────────► generate_report_task ──► PDF
```

To change the schedule, edit `beat_schedule` in `app/core/celery_app.py`:

```python
celery_app.conf.beat_schedule = {
    "daily-order-summary-report": {
        "task": "app.workers.scheduled_tasks.generate_daily_report",
        "schedule": crontab(hour=1, minute=0),  # change as needed
    },
}
```

---

## Retry Strategy

Transient errors (database blips, I/O errors) are retried with exponential backoff:

```
Attempt 1 ──► fail ──► wait 10s
Attempt 2 ──► fail ──► wait 20s
Attempt 3 ──► fail ──► wait 40s
Attempt 4 ──► FAILED (max retries exhausted)
```

Non-retryable errors (logic errors, missing records) fail immediately.

Both Celery's task state and the `Report.status` in PostgreSQL are kept consistent.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | _(required)_ | PostgreSQL connection string |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Redis broker URL |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` | Celery result backend |
| `STORAGE_PATH` | `storage/reports` | Directory for generated PDFs |
| `CELERY_TASK_ALWAYS_EAGER` | `False` | Run tasks synchronously (testing) |
| `TEST_DATABASE_URL` | `None` | Postgres URL for integration tests |

> **Note:** Docker Compose overrides `DATABASE_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` automatically to use internal service names (`db`, `redis`). Your `.env` file is used for local development only.

---

## Local Development (without Docker)

```bash
# Start dependencies
# (Postgres on 5432, Redis on 6379 must be running locally)

# Apply migrations
alembic upgrade head

# Start API
uvicorn app.main:app --reload

# Start worker (separate terminal)
celery -A app.core.celery_app.celery_app worker --loglevel=info -Q reports

# Start Beat scheduler (separate terminal)
celery -A app.core.celery_app.celery_app beat --loglevel=info
```

---

## License

MIT
