#!/bin/bash
# Откат деплоя book.auezov.edu.kz
#
# Запуск:  ~/book_site/book_ormk/rollback.sh            (на коммит до деплоя)
#          ~/book_site/book_ormk/rollback.sh d94d17a    (на указанный коммит)
#
# Откатывается ТОЛЬКО код. База не восстанавливается специально: миграция 0009
# лишь добавляет поле и таблицы, старый код с ними работает. Восстановление
# базы стёрло бы всё, что добавили после деплоя (см. подсказку в конце).
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
APP="$REPO/main/main"
TRIGGER="$(dirname "$REPO")/restart.txt"
BACKUPS="$HOME/backups"
PORT=2020
MARKER='hero-badge'

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
    LAST="$(ls -t "$BACKUPS"/commit-before-*.txt 2>/dev/null | head -1 || true)"
    [ -n "$LAST" ] || { echo "ОШИБКА: не найден файл с коммитом до деплоя, укажите его аргументом"; exit 1; }
    TARGET="$(cat "$LAST")"
    echo "коммит до деплоя: $TARGET (из $LAST)"
fi

echo "=== 1. Возвращаем код на $TARGET ==="
git -C "$REPO" reset --hard "$TARGET"
git -C "$REPO" rev-parse --short HEAD

echo "=== 2. Возвращаем миграцию 0008, если её убрал откат ==="
M008="$APP/main_app/migrations/0008_videolecture.py"
if [ ! -f "$M008" ]; then
    SAVED="$(ls -t "$BACKUPS"/0008_videolecture.py.* 2>/dev/null | head -1 || true)"
    if [ -n "$SAVED" ]; then
        cp "$SAVED" "$M008"
        echo "восстановлена из $SAVED"
    else
        echo "ВНИМАНИЕ: копия 0008 не найдена. Сайт работать будет, но"
        echo "makemigrations в будущем выдаст ошибку о пропущенной миграции."
    fi
fi

echo "=== 3. Перезапуск ==="
date > "$TRIGGER" 2>/dev/null || echo "не удалось записать $TRIGGER"
old=0
for _ in $(seq 1 15); do
    sleep 2
    if ! curl -s "http://127.0.0.1:$PORT/" | grep -q "$MARKER"; then
        old=1; break
    fi
done
if [ "$old" != 1 ]; then
    echo "!!! Сайт всё ещё на новом коде — попросите администратора: systemctl restart gunicorn"
    exit 2
fi

echo "=== 4. Проверка ==="
curl -sI "http://127.0.0.1:$PORT/" | head -2
echo "откат выполнен, сайт на старом коде"
echo
echo "Пакеты jazzmin/summernote/adminsortable2 удалять не нужно:"
echo "старый settings.py их не использует."
echo
echo "Если (и только если) повреждены данные, базу можно вернуть вручную:"
echo "  ls -t $BACKUPS/db-*.sqlite3 | head"
echo "  cp <нужная копия> $APP/db.sqlite3   # и ещё раз перезапустить"
