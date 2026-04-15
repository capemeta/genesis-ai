#!/bin/sh
set -eu

# 基于 docker/.env 中的数据库配置完成首次初始化，避免静态 SQL 与运行配置不一致。
DB_NAME="${DB_NAME:-genesis_ai}"
DB_USER="${DB_USER:-genesis_app}"
DB_PASSWORD="${DB_PASSWORD:-genesis_dev_password}"
DB_OWNER="${POSTGRES_USER:-postgres}"
SCHEMA_PATH="/opt/genesis/bootstrap/init-schema.sql"

psql -v ON_ERROR_STOP=1 \
  --username "$DB_OWNER" \
  --dbname postgres \
  --set db_name="$DB_NAME" \
  --set db_user="$DB_USER" \
  --set db_password="$DB_PASSWORD" \
  --set db_owner="$DB_OWNER" <<'EOSQL'
SELECT version();

-- psql 变量不会在 DO $$ ... $$ 里替换，这里改用 \gexec 动态执行。
SELECT format(
    'CREATE DATABASE %I WITH OWNER = %I ENCODING = %L LC_COLLATE = %L LC_CTYPE = %L TABLESPACE = pg_default CONNECTION LIMIT = -1',
    :'db_name',
    :'db_owner',
    'UTF8',
    'en_US.utf8',
    'en_US.utf8'
)
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'db_name')\gexec

SELECT format(
    'COMMENT ON DATABASE %I IS %L',
    :'db_name',
    'Genesis AI Platform - Development Database'
)\gexec

SELECT format(
    'CREATE USER %I WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION CONNECTION LIMIT -1 PASSWORD %L',
    :'db_user',
    :'db_password'
)
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = :'db_user')\gexec

SELECT format('ALTER USER %I WITH PASSWORD %L', :'db_user', :'db_password')\gexec

SELECT format(
    'COMMENT ON ROLE %I IS %L',
    :'db_user',
    'Genesis AI application user (limited privileges)'
)\gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'db_name', :'db_user')\gexec
EOSQL

psql -v ON_ERROR_STOP=1 \
  --username "$DB_OWNER" \
  --dbname "$DB_NAME" \
  --set db_name="$DB_NAME" \
  --set db_user="$DB_USER" \
  --set db_owner="$DB_OWNER" <<'EOSQL'
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "ltree";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'db_user')\gexec
SELECT format('GRANT CREATE ON SCHEMA public TO %I', :'db_user')\gexec
SELECT format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO %I', :'db_user')\gexec
SELECT format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO %I', :'db_user')\gexec
SELECT format('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO %I', :'db_user')\gexec

SELECT format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I',
    :'db_owner',
    :'db_user'
)\gexec

SELECT format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO %I',
    :'db_owner',
    :'db_user'
)\gexec

SELECT format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO %I',
    :'db_owner',
    :'db_user'
)\gexec

SELECT '✅ Database initialized successfully!' AS status;
SELECT '✅ Extensions installed successfully!' AS status;
SELECT '✅ Application user prepared successfully!' AS status;

SELECT
    datname AS database_name,
    pg_encoding_to_char(encoding) AS encoding,
    datcollate AS collation,
    datctype AS ctype,
    datconnlimit AS connection_limit
FROM pg_database
WHERE datname = :'db_name';

SELECT
    rolname AS username,
    rolsuper AS is_superuser,
    rolcreatedb AS can_create_db,
    rolcreaterole AS can_create_role
FROM pg_roles
WHERE rolname IN (:'db_owner', :'db_user')
ORDER BY rolname;

SELECT
    current_database() AS database_name,
    current_user AS current_user,
    version() AS postgres_version;
EOSQL

if [ -f "$SCHEMA_PATH" ]; then
  echo "📦 Importing business schema and seed data from $SCHEMA_PATH"
  psql -v ON_ERROR_STOP=1 \
    --username "$DB_OWNER" \
    --dbname "$DB_NAME" \
    -f "$SCHEMA_PATH"
fi
