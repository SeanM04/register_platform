# Registrar Academic Analytics Platform

UniStudio is a Django-based registrar intelligence platform for monitoring enrolment, academic performance, progression, programme performance, student risk, and operational insights from institutional CSV data.

## Platform Summary

The platform currently includes:

- `Dashboard` for institution-wide headline metrics with **optimized chart drill-downs** (10-100x performance improvements)
- `Students` for a searchable student directory with profile drill-down
- `Programmes` for programme-level performance summaries
- `Demographics` for gender and location-based breakdowns
- `Academic Levels` for year/semester level analysis
- `Completion Analysis` for semester completion, cohort shifting, and zero-completion drivers
- `Graduation Analysis` for cohort-based graduation rate summaries
- `Risk` for identifying at-risk students from academic outcomes
- `Insights` for operational recommendations and flagged-student context
- `System Management` for platform user administration and access control
- `UniStudio Chatbot` as a floating in-platform assistant with real-time status feedback and async streaming

## Technology Stack

- Python `3.13` local development baseline
- Django `6.0.3`
- PostgreSQL
- Pandas for CSV ingestion support
- Server-rendered templates with app-scoped CSS and JavaScript
- `uvicorn` (ASGI) for async views and SSE streaming — required for the chatbot streaming endpoint

## Documentation Map

- [README.md](README.md)
  Main project overview and quick-start guide
- [docs/README.md](docs/README.md)
  **Central documentation index with drill-down optimization details**
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
  Production deployment checklist and release flow
- [docs/OPERATIONS.md](docs/OPERATIONS.md)
  Day-to-day platform administration and data refresh runbook
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
  Application structure, data model, and technical design notes
- [docs/CHATBOT.md](docs/CHATBOT.md)
  Chatbot widget — async SSE streaming, real-time status feedback, 20-handler dispatch, rate limiting, and AI provider fallback
- [docs/pages/README.md](docs/pages/README.md)
  Page-by-page sidebar documentation with user explanations, architecture
  diagrams, file maps, and maintenance checks
- [docs/COMPLETION_ANALYTICS.md](docs/COMPLETION_ANALYTICS.md)
  Completion rules, effective cohort logic, narratives, and frontend file map
- [docs/GRADUATION_ANALYTICS.md](docs/GRADUATION_ANALYTICS.md)
  Graduation rules, effective cohorts, narratives, and frontend file map
- [docs/DRILLDOWN_OPTIMIZATION.md](docs/DRILLDOWN_OPTIMIZATION.md)
  **Comprehensive guide to drill-down performance optimizations (10-100x speed improvements)**
- [docs/DRILLDOWN_FRONTEND.md](docs/DRILLDOWN_FRONTEND.md)
  **Frontend implementation details for drill-down modals and pagination**
- [data/README.md](data/README.md)
  Source data expectations and CSV import guidance

## Quick Start

### 1. Activate the project environment

```powershell
cd C:\Users\Mukar\OneDrive\Desktop\uni_project
.\uni_project_env\Scripts\Activate.ps1
```

If PowerShell blocks activation in a new terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\uni_project_env\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Update the PostgreSQL settings in `.env` before continuing.

### 4. Create the PostgreSQL database

```sql
CREATE DATABASE registrar_dashboard;
```

### 5. Run database migrations

```powershell
python manage.py migrate
```

### 6. Create the first platform administrator

```powershell
python manage.py createsuperuser
```

Important notes:

- the platform uses email as the login identifier
- the custom user model is `accounts.User`
- the seeded access catalogue includes the `admin` role

### 7. Import academic data

```powershell
python manage.py import_registrar_data "C:\Users\Mukar\Downloads\Registrations.csv" "C:\Users\Mukar\Downloads\course final marks by period.csv" "C:\Users\Mukar\Downloads\completion_analysis_2026-04-17.csv"
```

### 8. Start the development server

**Standard (WSGI) — all features except live chatbot streaming:**

```powershell
python manage.py runserver
```

**With async streaming — required for real-time chatbot status updates:**

```powershell
uvicorn registrar_platform.asgi:application --reload
```

Default local URLs:

- application home: `http://127.0.0.1:8000/`
- login page: `http://127.0.0.1:8000/login/`
- Django admin: `http://127.0.0.1:8000/admin/`

> The chatbot works under both servers. Under `manage.py runserver` (WSGI) the client cycles through status messages client-side. Under `uvicorn` (ASGI) the server streams live step updates as they happen.

## Core Application Routes

- `/` dashboard landing page
- `/students/` student directory
- `/students/<slug>/` student profile
- `/programme/` programme performance
- `/demographic/` demographic analytics
- `/academic-level/` academic level analytics
- `/completion/` completion analytics
- `/graduation/` graduation analytics
- `/risk/` student risk monitor
- `/insights/` institutional insights
- `/system-management/` admin-only user management workspace
- `/login/` custom session login
- `/logout/` logout endpoint

### Chatbot API Routes

- `/api/chatbot/message/` JSON endpoint (sync, WSGI-compatible)
- `/api/chatbot/stream/` SSE streaming endpoint (async, requires ASGI/uvicorn)
- `/api/chatbot/clear/` clears the current session's conversation history

## Authentication Notes

This project does not use Django's default username-based login.

Current authentication design:

- custom `accounts.User` model based on `AbstractUser`
- email is the login identifier
- session authentication is the primary auth mechanism
- custom JSON login flow at `/login/`
- account lockout protection via `accounts.LoginLockout`
- session validation middleware to protect stale or malformed sessions
- built-in Django password reset views are still available under `/auth/...`

## Data Import Summary

The registrar import command currently loads:

- `Faculty`
- `Department`
- `Programme`
- `AcademicPeriod`
- `Student`
- `AttendanceType`
- `AcademicDecision`
- `Registration`
- `Course`
- `CourseResult`
- `Cohort`
- `ZeroCompletionReason`
- `CompletionAnalysisRecord`

Important behavior:

- the import is a full academic-data rebuild
- it clears previously imported academic entities before loading the new snapshot
- authentication and platform user accounts are not cleared by the import
- course results are matched to registrations using `registration_number + period_id`
- student age is calculated from `date_of_birth` during import
- the completion analysis export can be loaded as a third CSV argument and is decomposed into linked student, programme, decision, cohort, and zero-completion reason records

See [data/README.md](data/README.md) for the operational import guide.

## Completion Analytics Notes

The completion analysis implementation is documented in [docs/COMPLETION_ANALYTICS.md](docs/COMPLETION_ANALYTICS.md).

That guide explains:

- the shared rules in `services/completion_rules.py`
- the page aggregation service in `services/completion_service.py`
- the completion endpoints in `dashboard/completion/views.py`
- the AI and rule-based narratives flow in `dashboard/completion/ai_insights.py`
- the page shell, charts, and diagnostics wiring in `dashboard/templates/dashboard/completion.html`, `dashboard/static/dashboard/js/completion.js`, and `dashboard/static/dashboard/css/completion.css`

## Graduation Analytics Notes

The graduation analysis implementation is documented in [docs/GRADUATION_ANALYTICS.md](docs/GRADUATION_ANALYTICS.md).

That guide explains:

- the graduation aggregation service in `services/graduation_services.py`
- the graduation endpoints in `dashboard/graduation/views.py`
- the AI and rule-based narratives flow in `dashboard/graduation/ai_insights.py`
- the page shell, charts, and diagnostics wiring in `dashboard/templates/dashboard/graduation.html`, `dashboard/static/dashboard/js/graduation.js`, and `dashboard/static/dashboard/css/graduation.css`

## Quality Checks

Run these before handing the project over or deploying a release:

```powershell
python manage.py check
python manage.py check --deploy
python manage.py test
```

## Production Readiness Checklist

Before deployment:

- set `DJANGO_DEBUG=False`
- set a real `DJANGO_SECRET_KEY`
- set `DJANGO_ALLOWED_HOSTS`
- set `DJANGO_CSRF_TRUSTED_ORIGINS`
- verify PostgreSQL credentials
- run `python manage.py migrate`
- run `python manage.py collectstatic --noinput`
- run `python manage.py check --deploy`
- confirm the first admin user can log in

Detailed production guidance lives in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Project Structure

```text
uni_project/
|-- accounts/                    Custom authentication app
|-- chatbot/                     Chatbot app (models, views, middleware, URLs)
|   |-- middleware.py            Sliding-window rate limiter (30 req/60 s)
|   |-- views.py                 JSON endpoint + async SSE streaming endpoint
|-- dashboard/                   Core analytics app
|   |-- management/commands/     CSV import command
|   |-- migrations/
|   |-- static/dashboard/
|   |   |-- js/chatbot.js        Chatbot widget — SSE client + client-side status cycle
|   |   |-- css/chatbot.css      Chatbot widget styles
|   |-- templates/dashboard/
|-- services/
|   |-- chatbot_service.py       20-handler dispatch + AI provider fallback + status callbacks
|-- data/                        Optional local CSV staging area
|-- docs/                        Comprehensive documentation
|   |-- CHATBOT.md               Chatbot architecture, streaming, rate limiting, handlers
|   |-- DRILLDOWN_OPTIMIZATION.md    Performance optimization strategies (10-100x improvements)
|   |-- DRILLDOWN_FRONTEND.md        Frontend implementation details
|   |-- ARCHITECTURE.md              System architecture and design
|   |-- DEPLOYMENT.md                Production deployment guidance
|   |-- OPERATIONS.md                Day-to-day operations runbook
|   |-- README.md                    Documentation index and navigation hub
|-- registrar_platform/          Django project settings and root URLs
|-- static/                      Shared static root for project-wide assets
|-- templates/                   Shared base templates
|-- .env.example                 Environment variable template
|-- manage.py
|-- requirements.txt
```

## Useful Commands

```powershell
# Development
python manage.py runserver
uvicorn registrar_platform.asgi:application --reload

# Database
python manage.py migrate
python manage.py createsuperuser

# Data
python manage.py import_registrar_data "C:\Path\To\Registrations.csv" "C:\Path\To\course final marks by period.csv" "C:\Path\To\completion_analysis.csv"

# Quality
python manage.py test
python manage.py check --deploy
python manage.py collectstatic --noinput
```

## Troubleshooting

### The application starts but static assets look stale

- run a hard refresh in the browser
- if deploying, re-run `collectstatic --noinput`

### Login succeeds in Django admin but not on the platform

- remember that the platform login uses email, not username
- confirm the account is active
- confirm the account is not currently locked out

### The dashboards look empty after setup

- confirm migrations ran successfully
- confirm the CSV import completed successfully
- confirm the PostgreSQL database in `.env` is the same database the app is using

### The import command appears to lose existing academic data

That is expected. The import currently rebuilds the academic snapshot from the supplied CSV files.

## Status

The project is set up as a production-oriented internal analytics platform with:

- custom email-based authentication
- environment-driven security settings
- deployment-aware static file handling
- module-specific analytics pages
- destructive but repeatable CSV ingestion
- documented operational workflow
- in-platform AI chatbot with async SSE streaming, real-time status feedback, sliding-window rate limiting, and Google Gemini / OpenAI / rule-based fallback
