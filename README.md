# Bulk Certificate Generator

A FastAPI backend for submitting bulk certificate-generation jobs, tracking progress, and downloading the resulting PDF certificates. Each accepted recipient gets an individual certificate rendered from one predefined landscape A4 template.

## Features

- Accepts a recipient list in one request (1 to 500 recipients by default).
- Validates event details, recipient names, and email addresses before creating a job.
- Generates one PDF per recipient and isolates generation failures so the rest of the job can continue.
- Reports job and per-certificate status, including successful and failed counts.
- Supports optional PNG/JPG logos and controlled border styling.
- Uses SQLAlchemy with SQLite by default.

## Requirements

- Python 3.10 or later
- pip

## Setup

From the project root, create and activate a virtual environment, then install the dependencies.

### Windows PowerShell

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If Python 3.13 is unavailable, use another installed Python version supported by the dependencies, for example `py -3.10`.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run the application

With the virtual environment active:

```bash
python run.py
```

The development server listens at <http://127.0.0.1:8000>; open that address in a browser to use the frontend. The interface is also available at <http://127.0.0.1:8000/app>. Interactive API documentation is at <http://127.0.0.1:8000/docs>; ReDoc is at <http://127.0.0.1:8000/redoc>. The health endpoint is `GET /health`.

The frontend lets you create a certificate batch, enter recipients or import a CSV with `name,email` columns, optionally upload logos, customize the border, track generation, and download each completed PDF. To resume tracking a batch after refreshing the page, enter its batch ID in the status panel. Non-browser requests to `/` retain the JSON service-status response.

## Create a generation job

Send a JSON request to `POST /api/jobs`:

```bash
curl -X POST "http://127.0.0.1:8000/api/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "Cyber Security Workshop",
    "event_date": "2026-10-15",
    "recipients": [
      {"name": "Bhargavi Bayar", "email": "bhargavi@example.com"},
      {"name": "Rahul Kumar", "email": "rahul@example.com"}
    ]
  }'
```

The request returns HTTP `202 Accepted`, for example:

```json
{
  "job_id": 1,
  "status": "queued",
  "total_count": 2
}
```

Optional JSON fields are `border_style` (`none`, `single`, `double`, or `thick`), `border_color` (3- or 6-digit hex color), and `border_width` (1-10). Defaults are `double`, `#1E3A8A`, and `2`.

Invalid request data returns HTTP `422 Unprocessable Entity` and does not create a job. Event names must contain 1-255 characters; recipient names 1-150 characters; emails must be valid; and each job accepts 1-500 recipients by default.

## Track progress and get certificate IDs

Poll `GET /api/jobs/{job_id}` until the status is final:

```bash
curl "http://127.0.0.1:8000/api/jobs/1"
```

The response includes `status`, `total_count`, `success_count`, `failure_count`, `pending_count`, and `progress_percentage`. Job statuses are `queued`, `processing`, `completed`, `completed_with_errors`, and `failed`.

To inspect recipients and their individual results, request `GET /api/jobs/{job_id}/certificates`:

```bash
curl "http://127.0.0.1:8000/api/jobs/1/certificates"
```

Each record includes its `id`, recipient details, status, and an `error_message` when generation failed. The list endpoint returns metadata, not PDF contents.

## Download a generated certificate

Use a completed certificate's `id` from the list response:

```bash
curl -L "http://127.0.0.1:8000/api/certificates/1" --output certificate.pdf
```

The endpoint streams an `application/pdf` file. It returns `404` when the certificate or file is missing, `409` while generation is pending or processing, and `400` when generation failed.

## Optional logo upload

`POST /api/jobs/upload` accepts `multipart/form-data` with `event_name`, `event_date`, `recipients` (a JSON array encoded as a string), and optional border fields. Supply zero to ten `logos` files; accepted formats are PNG, JPG, and JPEG, with a 2 MB maximum per file. Uploaded logos are included in each certificate in that job.

The `/docs` page provides an interactive form for this endpoint. A cURL example is:

```bash
curl -X POST "http://127.0.0.1:8000/api/jobs/upload" \
  -F 'event_name=Cyber Security Workshop' \
  -F 'event_date=2026-10-15' \
  -F 'recipients=[{"name":"Bhargavi Bayar","email":"bhargavi@example.com"}]' \
  -F 'logos=@logo.png'
```

## Configuration and generated files

Settings can be provided as environment variables or in a `.env` file in the project root:

| Setting | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./bulk_certificates.db` | SQLAlchemy database URL |
| `CERTIFICATES_DIR` | `generated_certificates` | Directory for generated PDFs and uploaded logos |
| `MAX_RECIPIENTS_PER_JOB` | `500` | Maximum recipients in one job |
| `MAX_LOGOS_PER_JOB` | `10` | Maximum logos in one job |
| `MAX_LOGO_FILE_SIZE_BYTES` | `2097152` | Maximum size of each logo upload |

The database tables are initialized when the application starts. Certificate PDFs are stored in `CERTIFICATES_DIR`; uploaded logos are stored under its `logos/` subdirectory. Keep both the database and generated files if you need to preserve job history and downloads.

## Run tests

From the project root with the virtual environment active:

```bash
pytest -q
```

The test suite uses an isolated in-memory SQLite database and covers job creation, validation, certificate generation and retrieval, progress tracking, logo and border handling, and individual-generation failure isolation.

## Implementation decisions

- **Bulk job API:** One request validates and records all recipients, then returns a job ID so clients can poll rather than wait for every PDF to finish.
- **Background processing:** FastAPI `BackgroundTasks` processes recipients after the response is accepted. Each recipient is handled independently; its result is committed and a failure is recorded without stopping later recipients.
- **Process-local task execution:** This lightweight approach avoids an external queue for the assignment. Tasks are not durable across process termination; a production deployment needing reliable recovery or multiple workers should move processing to a persistent queue such as Celery or RQ.
- **Relational persistence:** SQLAlchemy models store job and certificate records. SQLite is the zero-configuration local default; `DATABASE_URL` can be changed to another SQLAlchemy-supported database when its driver is installed.
- **Fixed certificate design:** ReportLab renders one predefined landscape A4 PDF template. Border options and optional logos customize an issued certificate without introducing a template editor.
- **Failure visibility:** Input validation rejects an invalid request as a whole. Errors encountered during PDF generation are stored on the affected certificate, reflected in job counts, and do not prevent other recipients from being processed.