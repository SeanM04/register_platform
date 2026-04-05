# Deployment Guide

This document is the production deployment runbook for the UniStudio registrar analytics platform.

## 1. Deployment Model

Current application architecture:

- Django web application
- PostgreSQL primary database
- server-rendered UI with collected static files
- custom session-based authentication

Recommended production topology:

- Django application server
- reverse proxy or web server in front
- PostgreSQL on a managed or controlled host
- HTTPS termination at the proxy or ingress layer

The repository is ready for deployment at the Django configuration layer. Choose an application server appropriate to your operating system and hosting environment.

## 2. Pre-Deployment Checklist

Before releasing:

- production database created
- environment variables prepared
- secret key generated
- allowed hosts and trusted origins confirmed
- TLS/HTTPS plan in place
- first administrator account identified
- latest academic CSV snapshot available if a fresh data load is required

## 3. Required Environment Variables

Minimum required values:

```env
DJANGO_SECRET_KEY=replace-with-a-long-random-secret
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.com,www.your-domain.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain.com,https://www.your-domain.com

POSTGRES_DB=registrar_dashboard
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
```

Security-related defaults supported by the project:

```env
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
DJANGO_SECURE_HSTS_SECONDS=31536000
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=True
DJANGO_SECURE_HSTS_PRELOAD=True
DJANGO_SECURE_REFERRER_POLICY=strict-origin-when-cross-origin
DJANGO_X_FRAME_OPTIONS=DENY
```

Optional auth behavior:

```env
AUTH_LOCKOUT_FAILURE_LIMIT=5
AUTH_LOCKOUT_DURATION_MINUTES=15
LOGIN_BYPASS_DOMAINS=
```

## 4. Release Sequence

### 4.1 Prepare the environment

```powershell
python -m pip install -r requirements.txt
```

### 4.2 Run database migrations

```powershell
python manage.py migrate
```

### 4.3 Collect static files

```powershell
python manage.py collectstatic --noinput
```

### 4.4 Validate the release

```powershell
python manage.py check
python manage.py check --deploy
python manage.py test
```

### 4.5 Create the first administrator if needed

```powershell
python manage.py createsuperuser
```

### 4.6 Load academic data if required

```powershell
python manage.py import_registrar_data "C:\Path\To\Registrations.csv" "C:\Path\To\course final marks by period.csv"
```

Important:

- the import command rebuilds academic data
- do not run it casually in production without understanding the impact
- platform users and authentication data are not removed by the import

## 5. Post-Deployment Validation

After the release, confirm:

- `/login/` loads correctly
- the first admin can sign in using email
- `/system-management/` is accessible to the admin user
- dashboard pages render without template or static errors
- metrics endpoints load correctly
- static assets resolve in the browser

Key routes to validate:

- `/`
- `/students/`
- `/programme/`
- `/risk/`
- `/insights/`
- `/system-management/`

## 6. Static File Behavior

Production static storage uses `ManifestStaticFilesStorage` when `DJANGO_DEBUG=False`.

That means:

- `collectstatic --noinput` must be part of every production release
- stale references usually indicate an old browser cache or missed static collection step

## 7. Database Notes

The application expects PostgreSQL and does not ship with a SQLite fallback.

Operational cautions:

- keep regular PostgreSQL backups
- take a backup before running destructive academic data refreshes
- confirm `.env` points to the correct database before importing data

## 8. Authentication and Security Notes

This project uses:

- custom `accounts.User`
- email-based login
- session auth
- login lockout protection
- secure-cookie and HSTS support
- password reset routes from Django auth

Do not deploy with:

- `DJANGO_DEBUG=True`
- a placeholder secret key
- blank allowed hosts

## 9. Rollback Considerations

If a release fails:

- restore the previous code release
- restore the previous static files if needed
- restore the database only if a migration or destructive import created data inconsistency

For CSV imports specifically:

- keep the previous academic snapshot or a database backup before running the import

## 10. Handover Notes

A production handoff should include:

- deployed environment variables
- database host details
- backup ownership
- first admin account owner
- deployment server or hosting details
- a copy of the current academic import files or their source location
