## Data Import Staging Area

This folder can hold project-local copies of the registrar CSV files used to refresh academic data.

## Expected Source Files

- `Registrations.csv`
  Registration-level academic snapshot
- `course final marks by period.csv`
  Period-specific course marks and grading information

## Import Command

Run the import from the project root:

```powershell
python manage.py import_registrar_data "C:\Users\Mukar\Downloads\Registrations.csv" "C:\Users\Mukar\Downloads\course final marks by period.csv"
```

If you keep project-local copies in this folder, the command can also be run as:

```powershell
python manage.py import_registrar_data ".\data\Registrations.csv" ".\data\course final marks by period.csv"
```

## Important Behavior

- the importer clears previously imported academic data before rebuilding it
- the importer does not remove platform users or authentication data
- course results are matched to registrations by `regnum + period_id`

## Operational Guidance

Before running an import:

- confirm you are connected to the correct PostgreSQL database
- back up the database if the environment is shared or production-facing
- verify the CSV snapshot is the approved reporting version

After running an import:

- load the dashboard home page
- spot-check `Students`, `Programmes`, and `Risk`
- open at least one student profile to confirm drill-down data is present
