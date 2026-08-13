#!/bin/bash

set -euo pipefail

: "${MYSQL_SERVICE_ID:?MYSQL_SERVICE_ID is required}"
: "${POSTGRES_SERVICE_ID:?POSTGRES_SERVICE_ID is required}"

REPO_ROOT=$(dirname "$(dirname "$(realpath "${BASH_SOURCE[0]}")")")
CERT_DIR=${DB_CERT_DIR:-${RUNNER_TEMP:-${REPO_ROOT}}/db-certs}
DIST_DIR=${PYODIDE_DIST_DIR:-${REPO_ROOT}/dist}

export MYSQL_HOST=${MYSQL_HOST:-127.0.0.1}
export MYSQL_PORT=${MYSQL_PORT:-3306}
export MYSQL_USER=${MYSQL_USER:-root}
export MYSQL_PASSWORD=${MYSQL_PASSWORD:-pyodide_root_pw}
export MYSQL_CA_FILE=${CERT_DIR}/mysql-ca.pem
export POSTGRES_HOST=${POSTGRES_HOST:-127.0.0.1}
export POSTGRES_VERIFY_HOST=${POSTGRES_VERIFY_HOST:-localhost}
export POSTGRES_PORT=${POSTGRES_PORT:-5432}
export POSTGRES_USER=${POSTGRES_USER:-postgres}
export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-pyodide_root_pw}
export POSTGRES_DB=${POSTGRES_DB:-postgres}
export POSTGRES_CA_FILE=${CERT_DIR}/postgres/ca.crt

mkdir -p "${CERT_DIR}/postgres"

docker cp \
  "${MYSQL_SERVICE_ID}:/var/lib/mysql/ca.pem" \
  "${MYSQL_CA_FILE}"

openssl genrsa -out "${CERT_DIR}/postgres/ca.key" 2048
openssl req -x509 -new -nodes \
  -key "${CERT_DIR}/postgres/ca.key" \
  -sha256 \
  -days 1 \
  -out "${POSTGRES_CA_FILE}" \
  -subj "/CN=pyodide-postgres-ca"
openssl genrsa -out "${CERT_DIR}/postgres/server.key" 2048
openssl req -new \
  -key "${CERT_DIR}/postgres/server.key" \
  -out "${CERT_DIR}/postgres/server.csr" \
  -subj "/CN=localhost"
cat > "${CERT_DIR}/postgres/server-ext.cnf" <<'EOF'
subjectAltName=DNS:localhost,IP:127.0.0.1
extendedKeyUsage=serverAuth
EOF
openssl x509 -req \
  -in "${CERT_DIR}/postgres/server.csr" \
  -CA "${POSTGRES_CA_FILE}" \
  -CAkey "${CERT_DIR}/postgres/ca.key" \
  -CAcreateserial \
  -out "${CERT_DIR}/postgres/server.crt" \
  -days 1 \
  -sha256 \
  -extfile "${CERT_DIR}/postgres/server-ext.cnf"

docker cp \
  "${CERT_DIR}/postgres/server.crt" \
  "${POSTGRES_SERVICE_ID}:/var/lib/postgresql/data/server.crt"
docker cp \
  "${CERT_DIR}/postgres/server.key" \
  "${POSTGRES_SERVICE_ID}:/var/lib/postgresql/data/server.key"
docker cp \
  "${POSTGRES_CA_FILE}" \
  "${POSTGRES_SERVICE_ID}:/var/lib/postgresql/data/root.crt"
docker exec -u root "${POSTGRES_SERVICE_ID}" sh -c \
  'chown postgres:postgres /var/lib/postgresql/data/server.crt /var/lib/postgresql/data/server.key /var/lib/postgresql/data/root.crt && chmod 600 /var/lib/postgresql/data/server.key'
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" \
  "${POSTGRES_SERVICE_ID}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
  -c "ALTER SYSTEM SET ssl = 'on';"
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" \
  "${POSTGRES_SERVICE_ID}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
  -c "ALTER SYSTEM SET ssl_cert_file = 'server.crt';"
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" \
  "${POSTGRES_SERVICE_ID}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
  -c "ALTER SYSTEM SET ssl_key_file = 'server.key';"

docker restart "${POSTGRES_SERVICE_ID}"

for attempt in {1..30}; do
  if docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" \
    "${POSTGRES_SERVICE_ID}" pg_isready \
    -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"; then
    break
  fi
  if [[ "${attempt}" -eq 30 ]]; then
    echo "PostgreSQL service failed to become ready after TLS restart" >&2
    exit 1
  fi
  sleep 2
done

pytest -v \
  --dist-dir="${DIST_DIR}" \
  --runner=selenium \
  --rt node \
  -m db \
  --junitxml="${REPO_ROOT}/test-results-db.xml" \
  "${REPO_ROOT}/packages/mysqlclient/test_mysqlclient_e2e.py" \
  "${REPO_ROOT}/packages/psycopg/test_psycopg_e2e.py"
