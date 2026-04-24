@echo off
echo Resetting PostgreSQL password...

REM Create a temporary pg_hba.conf for password reset
echo "local all all trust" > "C:\Program Files\PostgreSQL\18\data\pg_hba.conf.tmp"
echo "host all all 127.0.0.1/32 trust" >> "C:\Program Files\PostgreSQL\18\data\pg_hba.conf.tmp"

REM Backup original config
copy "C:\Program Files\PostgreSQL\18\data\pg_hba.conf" "C:\Program Files\PostgreSQL\18\data\pg_hba.conf.backup"

REM Use temporary config
copy "C:\Program Files\PostgreSQL\18\data\pg_hba.conf.tmp" "C:\Program Files\PostgreSQL\18\data\pg_hba.conf"

REM Start PostgreSQL service
net start postgresql-x64-18

REM Wait for service to start
timeout /t 5 /nobreak

REM Set new password
"C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "ALTER USER postgres PASSWORD 'admin123';"

REM Restore original config
copy "C:\Program Files\PostgreSQL\18\data\pg_hba.conf.backup" "C:\Program Files\PostgreSQL\18\data\pg_hba.conf"

REM Restart PostgreSQL service
net stop postgresql-x64-18
net start postgresql-x64-18

echo PostgreSQL password reset to: admin123
echo Please update your .env file with POSTGRES_PASSWORD=admin123

REM Cleanup
del "C:\Program Files\PostgreSQL\18\data\pg_hba.conf.tmp"
del "C:\Program Files\PostgreSQL\18\data\pg_hba.conf.backup"

pause
