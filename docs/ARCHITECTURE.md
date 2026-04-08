# Architecture Overview

This document describes the current structure of the UniStudio registrar analytics platform.

## 1. Application Shape

The project is split into three main areas:

- `registrar_platform`
  Django project configuration, root settings, and top-level URLs
- `accounts`
  Custom authentication, lockout handling, session validation, and auth tests
- `dashboard`
  Academic data models, CSV ingestion, analytics views, templates, static assets, and dashboard tests

## 2. Authentication Design

Authentication is implemented in the `accounts` app.

Key elements:

- `accounts.User`
  Custom user model based on `AbstractUser`
- `accounts.UserType`
  Role catalogue for platform access
- `accounts.LoginLockout`
  Failed-attempt and lockout tracking by IP and identifier

Important settings:

- `AUTH_USER_MODEL = "accounts.User"`
- email is the `USERNAME_FIELD`
- authentication backends include a custom lockout backend and Django's `ModelBackend`
- session validation middleware is active

User-facing login behavior:

- `/login/` handles both GET and POST
- POST returns JSON responses for success, invalid credentials, and lockout state
- `/logout/` logs the user out and redirects to the login page

## 3. Academic Data Model

The `dashboard` app currently centers on these entities:

- `Faculty`
- `Department`
- `Programme`
- `AcademicPeriod`
- `Student`
- `Registration`
- `Course`
- `CourseResult`

Relationship summary:

- a `Faculty` has many `Department` records
- a `Department` has many `Programme` records
- a `Student` has many `Registration` records
- a `Registration` belongs to one `Programme` and one `AcademicPeriod`
- a `Registration` has many `CourseResult` records
- a `CourseResult` links one `Course` to one `Registration`

## 4. Import Pipeline

Academic data is loaded through:

- `dashboard.management.commands.import_registrar_data`

Source files:

- registrations CSV
- marks CSV

Current import flow:

1. validate the two input paths
2. clear previously imported academic entities
3. rebuild faculties, departments, programmes, periods, students, and registrations from the registrations CSV
4. match marks to registrations by `regnum + period_id`
5. create or update course and course-result records

Operational consequence:

- this is a full academic snapshot rebuild, not an incremental sync

## 5. UI Architecture

The frontend uses:

- Django templates
- app-scoped CSS
- lightweight page-scoped JavaScript

Key shared layout:

- `templates/base.html`

Static asset structure:

- `dashboard/static/dashboard/css/`
- `dashboard/static/dashboard/js/`
- `dashboard/static/dashboard/images/`
- `accounts/static/accounts/css/`
- `accounts/static/accounts/js/`

## 6. Dashboard Page Pattern

Most analytics pages follow a common structure:

- shared top filter bar
- summary metric cards
- story banner plus focused chart chapters for the richer analytics pages
- action register or primary data table lower on the page when operational follow-up is needed
- server-rendered data with light JS enhancement

Several metrics panels are hydrated asynchronously so the page shell can load quickly before expensive summaries resolve.

The landing dashboard now follows that async pattern explicitly:

- a lightweight shell from `dashboard/overview/views.py`
- a separate payload endpoint for the heavier chart datasets
- a separate narratives endpoint for optional AI-assisted chart copy
- page-scoped browser modules in `dashboard/static/dashboard/js/home/`
- shared topbar and filter layout styling in `templates/base.html` and
  `dashboard/static/dashboard/css/base.css`

The dashboard backend is also moving toward feature-owned packages inside `dashboard/` for the
more complex analytics pages. Current examples:

- `dashboard/academic_levels/`
- `dashboard/demographics/`
- `dashboard/overview/`
- `dashboard/risk/`
- `dashboard/insights/`

## 7. Current Modules

The dashboard app currently includes these view modules:

- home dashboard
- students
- student detail
- programmes
- demographics
- academic levels
- risk
- insights
- system management

## 8. Risk and Insights Logic

The risk and insights pages derive their content from academic signals already present in the imported dataset.

Current examples:

- average mark
- failed modules
- carried modules
- registration decision
- faculty or programme concentration

The UI now uses clearer, university-friendly labels such as:

- `Year 1, Semester 1`
- `Year 4, Semester 2`

instead of compressed technical labels like `1.1` or `4.2`.

The risk page now also follows the same richer feature pattern as academic levels and
demographics:

- backend ownership in `dashboard/risk/`
- page-scoped JS modules in `dashboard/static/dashboard/js/risk/`
- ECharts-based storytelling sections ahead of the action register
- safe AI-assisted overview narratives with deterministic fallbacks

The insights page now follows that same feature-owned pattern as well:

- backend ownership in `dashboard/insights/`
- page-scoped JS modules in `dashboard/static/dashboard/js/insights/`
- ECharts-based storytelling sections for executive cross-feature monitoring
- safe AI-assisted overview narratives with deterministic fallbacks

## 9. Quality and Test Coverage

The project includes automated tests for:

- authentication flow
- lockout behavior
- logout behavior
- protected AJAX endpoint access
- dashboard filters
- programme metrics
- risk view behavior and AI narrative fallbacks
- insights content
- system management access

Primary test modules:

- `accounts/tests.py`
- `dashboard/tests.py`
- `dashboard/academic_levels/tests.py`
- `dashboard/demographics/tests.py`
- `dashboard/overview/tests.py`
- `dashboard/risk/tests.py`
- `dashboard/insights/tests.py`

## 10. Production Notes

The project is configured for production-oriented deployment with:

- environment-driven secret key and host configuration
- secure-cookie settings
- HSTS support
- manifest static files in non-debug mode
- PostgreSQL as the primary database

Deployment details are documented in [DEPLOYMENT.md](DEPLOYMENT.md).

The landing dashboard's async shell and narrative flow are documented in
[DASHBOARD_HOME.md](DASHBOARD_HOME.md).
