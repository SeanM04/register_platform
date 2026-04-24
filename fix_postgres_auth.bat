@echo off
echo Fixing PostgreSQL authentication...

REM Stop PostgreSQL service
net stop postgresql-x64-18

REM Backup original pg_hba.conf
copy "C:\Program Files\PostgreSQL\18\data\pg_hba.conf" "C:\Program Files\PostgreSQL\18\data\pg_hba.conf.backup"

REM Create temporary pg_hba.conf with trust authentication
(
echo # TYPE  DATABASE        USER            ADDRESS                 METHOD
echo local   all             all                                     trust
echo host    all             all             127.0.0.1/32            trust
echo host    all             all             ::1/128                 trust
) > "C:\Program Files\PostgreSQL\18\data\pg_hba.conf"

REM Start PostgreSQL service
net start postgresql-x64-18

REM Wait for service to start
timeout /t 3 /nobreak

REM Connect and reset password
"C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "ALTER USER postgres PASSWORD 'admin123';"

REM Restore original pg_hba.conf
copy "C:\Program Files\PostgreSQL\18\data\pg_hba.conf.backup" "C:\Program Files\PostgreSQL\18\data\pg_hba.conf"

REM Restart PostgreSQL service
net stop postgresql-x64-18
net start postgresql-x64-18

echo PostgreSQL password reset to: admin123
echo Configuration restored

REM Cleanup
del "C:\Program Files\PostgreSQL\18\data\pg_hba.conf.backup"

pause
