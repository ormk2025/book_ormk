#!/bin/bash
# Откат кода на коммит до последнего обновления: /srv/book/book_ormk/rollback.sh
# Или на указанный коммит:                       /srv/book/book_ormk/rollback.sh abc1234
#
# База и media не меняются. Если обновление содержало миграцию, несовместимую
# со старым кодом, базу нужно вернуть вручную из копии в /srv/book/backups.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$REPO")"
BACKUPS="$ROOT/backups"

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
    LAST="$(ls -t "$BACKUPS"/commit-before-*.txt 2>/dev/null | head -1 || true)"
    [ -n "$LAST" ] || { echo "ОШИБКА: укажите коммит аргументом"; exit 1; }
    TARGET="$(cat "$LAST")"
fi

git -C "$REPO" reset --hard "$TARGET"
sudo systemctl restart book.service
sleep 3
curl -fsS -o /dev/null -w 'ответ сайта: %{http_code}\n' http://127.0.0.1:2020/
echo "Откат на $TARGET выполнен"
