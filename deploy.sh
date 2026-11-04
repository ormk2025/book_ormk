#!/bin/bash
# Обновление сайта на сервере: /srv/book/book_ormk/deploy.sh
#
# Скрипт останавливается на первой ошибке. Всё рискованное выполняется до
# перезапуска: пока gunicorn не перезапущен, пользователи видят старую версию.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
APP="$REPO/main/main"
ROOT="$(dirname "$REPO")"
BACKUPS="$ROOT/backups"
PY="$ROOT/venv/bin/python"
PIP="$ROOT/venv/bin/pip"
SOCKET_URL="http://127.0.0.1:2020/"
STAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUPS"
cd "$APP"

echo "=== 1. Копия базы ==="
"$PY" - "$BACKUPS/db-$STAMP.sqlite3" <<'PYEOF'
import sqlite3, sys
src = sqlite3.connect('db.sqlite3')
dst = sqlite3.connect(sys.argv[1])
with dst:
    src.backup(dst)
src.close(); dst.close()
print('копия:', sys.argv[1])
PYEOF
git -C "$REPO" rev-parse --short HEAD > "$BACKUPS/commit-before-$STAMP.txt"

echo "=== 2. Код ==="
git -C "$REPO" pull --ff-only origin main

echo "=== 3. Зависимости ==="
"$PIP" install -r requirements.txt

echo "=== 4. Проверка конфигурации ==="
"$PY" manage.py check

echo "=== 5. Миграции ==="
"$PY" manage.py migrate --noinput

echo "=== 6. Статика ==="
"$PY" manage.py collectstatic --noinput

echo "=== 7. Перезапуск ==="
sudo systemctl restart book.service
sleep 3
curl -fsS -o /dev/null -w 'ответ сайта: %{http_code}\n' "$SOCKET_URL"

echo "ГОТОВО. Откат: $REPO/rollback.sh"
