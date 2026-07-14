#!/usr/bin/env bash
#
# Odswiezenie lokalnej bazy danych kopia z Heroku Postgres.
#
# Co robi:
#   1. Dropuje lokalna baze (jesli istnieje) — pg:pull nie nadpisuje istniejacej.
#   2. Ciagnie schemat + dane 1:1 z Heroku (`heroku pg:pull`).
#   3. Anonimizuje dane osobowe (PII) w lokalnej kopii.
#
# Wymagania: uruchomiony lokalny Postgres, zalogowany `heroku` CLI.
# Uruchamiaj z katalogu backendu, przy zatrzymanym runserverze.
#
# Uzycie:
#   ./refresh-local-db.sh                 # domyslnie z domy-production
#   APP=domy-staging ./refresh-local-db.sh
#   SKIP_ANONYMIZE=1 ./refresh-local-db.sh
#
set -euo pipefail

APP="${APP:-domy-production}"
LOCAL_DB="${LOCAL_DB:-domy_local}"
HEROKU_DB_ATTACHMENT="${HEROKU_DB_ATTACHMENT:-DATABASE_URL}"

echo "==> Odswiezam '${LOCAL_DB}' danymi z aplikacji Heroku '${APP}'"

echo "==> Dropuje istniejaca baze '${LOCAL_DB}' (jesli jest)"
dropdb --if-exists "${LOCAL_DB}"

echo "==> heroku pg:pull ${HEROKU_DB_ATTACHMENT} -> ${LOCAL_DB}"
heroku pg:pull "${HEROKU_DB_ATTACHMENT}" "${LOCAL_DB}" --app "${APP}"

# Anonimizacja PII wylaczona na zyczenie — odkomentuj, jesli bedzie potrzebna.
# if [ "${SKIP_ANONYMIZE:-0}" = "1" ]; then
#     echo "==> Pomijam anonimizacje (SKIP_ANONYMIZE=1)"
# else
#     echo "==> Anonimizuje dane osobowe"
#     python manage.py anonymize_local --yes --keep-superusers
# fi

echo "==> Gotowe. Lokalna baza '${LOCAL_DB}' odswiezona z '${APP}'."
