# Operations Guide

This document covers day-to-day administration of the UniStudio platform.

## 1. Access and Login

Login route:

- `/login/`

Authentication behavior:

- users sign in with email
- the project uses Django sessions
- failed login attempts are tracked and may trigger lockout

If a user cannot log in:

- confirm the account is active
- confirm the email address is correct
- check whether the account is locked out after repeated failed attempts

## 2. User Administration

Primary user-management workspace:

- `/system-management/`

System Management supports:

- creating platform users
- activating or deactivating accounts
- clearing lockouts
- reviewing current access status

Access note:

- this page is intended for administrator-level users

## 3. Academic Data Refresh

Academic data is loaded through the management command below:

```powershell
python manage.py import_registrar_data "C:\Path\To\Registrations.csv" "C:\Path\To\course final marks by period.csv"
```

Operational behavior:

- academic data is cleared and rebuilt from the supplied CSV files
- authentication records are not removed
- the import should be treated as a controlled refresh step

Before running the import:

- confirm you are pointing at the correct database
- back up the production database
- confirm the CSV files are the approved snapshot for that cycle

## 4. Daily Platform Checks

Recommended quick checks after a deployment or import:

- log into the platform
- open the dashboard landing page
- open the `Students`, `Programmes`, and `Risk` pages
- confirm filters still work
- confirm at least one student profile opens correctly

## 5. Core Functional Areas

### Dashboard

Institution-level overview metrics and filtered summary cards.

### Students

Directory of students with one row per student and drill-down profile pages.

### Programmes

Programme performance view across faculties and departments.

### Demographics

Gender and place-of-birth breakdowns from imported student records.

### Academic Levels

Academic analysis grouped into user-friendly year and semester labels.

### Risk

At-risk student monitor based on academic signals such as failed modules, carrying load, and registration decision outcomes.

### Insights

Operational recommendations and flagged-student context derived from live data.

## 6. Risk Module Interpretation

The current risk presentation uses academic performance signals already present in the imported data.

Examples of drivers include:

- multiple failed modules
- carried modules
- adverse registration decisions such as retake

The UI removes redundant wording where a below-50 outcome is already implied by the risk state.

## 7. Troubleshooting

### A user is locked out

- clear the lockout from `System Management`
- if needed, verify lockout records in `accounts.LoginLockout`

### The platform shows no academic records

- confirm the import ran successfully
- confirm the application is using the expected PostgreSQL database

### The UI shows old styling or stale images

- hard refresh the browser
- if in production, re-run `collectstatic --noinput`

### A CSV import skips some marks

Current matching logic links marks to registrations by:

- `regnum`
- `period_id`

If those fields do not align across the two source files, unmatched marks will be skipped.

## 8. Recommended Operational Commands

```powershell
python manage.py check
python manage.py test
python manage.py showmigrations
python manage.py createsuperuser
python manage.py collectstatic --noinput
```
