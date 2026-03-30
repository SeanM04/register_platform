# Registrar Academic Analytics Platform

UniStudio is a Django-based registrar intelligence platform for monitoring enrolment, academic performance, progression, programme performance, student risk, and operational insights from institutional CSV data.

## Platform Summary

The platform currently includes:

- `Dashboard` for institution-wide headline metrics
- `Students` for a searchable student directory with profile drill-down
- `Programmes` for programme-level performance summaries
- `Demographics` for gender and location-based breakdowns
- `Academic Levels` for year/semester level analysis
- `Risk` for identifying at-risk students from academic outcomes
- `Insights` for operational recommendations and flagged-student context
- `System Management` for platform user administration and access control

## Technology Stack

- Python `3.13` local development baseline
- Django `6.0.3`
- PostgreSQL
- Pandas for CSV ingestion support
- Server-rendered templates with app-scoped CSS and JavaScript

## Documentation Map

- [README.md](README.md)
  Main project overview and quick-start guide
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
  Production deployment checklist and release flow
- [docs/OPERATIONS.md](docs/OPERATIONS.md)
  Day-to-day platform administration and data refresh runbook
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
  Application structure, data model, and technical design notes
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
python manage.py import_registrar_data "C:\Users\Mukar\Downloads\Registrations.csv" "C:\Users\Mukar\Downloads\course final marks by period.csv"
```

### 8. Start the development server

```powershell
python manage.py runserver
```

Default local URLs:

- application home: `http://127.0.0.1:8000/`
- login page: `http://127.0.0.1:8000/login/`
- Django admin: `http://127.0.0.1:8000/admin/`

## Core Application Routes

- `/` dashboard landing page
- `/students/` student directory
- `/students/<slug>/` student profile
- `/programme/` programme performance
- `/demographic/` demographic analytics
- `/academic-level/` academic level analytics
- `/risk/` student risk monitor
- `/insights/` institutional insights
- `/system-management/` admin-only user management workspace
- `/login/` custom session login
- `/logout/` logout endpoint

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
- `Registration`
- `Course`
- `CourseResult`

Important behavior:

- the import is a full academic-data rebuild
- it clears previously imported academic entities before loading the new snapshot
- authentication and platform user accounts are not cleared by the import
- course results are matched to registrations using `registration_number + period_id`

See [data/README.md](data/README.md) for the operational import guide.

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
|-- dashboard/                   Core analytics app
|   |-- management/commands/     CSV import command
|   |-- migrations/
|   |-- static/dashboard/
|   |-- templates/dashboard/
|-- data/                        Optional local CSV staging area
|-- docs/                        Deployment, operations, and architecture docs
|-- registrar_platform/          Django project settings and root URLs
|-- static/                      Shared static root for project-wide assets
|-- templates/                   Shared base templates
|-- .env.example                 Environment variable template
|-- manage.py
|-- requirements.txt
```

## Useful Commands

```powershell
python manage.py runserver
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py import_registrar_data "C:\Path\To\Registrations.csv" "C:\Path\To\course final marks by period.csv"
python manage.py test
python manage.py check --deploy
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
