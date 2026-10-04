#!/bin/bash
# Деплой book.auezov.edu.kz
#
# Запуск на сервере по SSH:   ~/book_site/book_ormk/deploy.sh
#
# Скрипт останавливается на первой ошибке. Всё рискованное сделано ДО
# перезапуска: пока gunicorn не перезапущен, пользователи видят старый сайт.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
APP="$REPO/main/main"
TRIGGER="$(dirname "$REPO")/restart.txt"   # ~/book_site/restart.txt
BACKUPS="$HOME/backups"
PORT=2020
MARKER='hero-badge'          # есть только в новом шаблоне главной страницы
STAMP="$(date +%Y%m%d-%H%M)"

# venv внутри chroot и на хосте доступен по разным путям
VENV=""
for c in "$HOME/venv" /var/www/clients/client3/web71/home/aidasshbook/venv; do
    [ -x "$c/bin/python" ] && VENV="$c" && break
done
[ -n "$VENV" ] || { echo "ОШИБКА: не найден venv с работающим python"; exit 1; }
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"

mkdir -p "$BACKUPS"
cd "$APP"

echo "=== 0. Окружение ==="
echo "venv:   $VENV"
"$PY" -V
"$PY" -c "import django; print('Django', django.get_version())"

echo "=== 1. Резервная копия базы ==="
"$PY" - "$BACKUPS/db-$STAMP.sqlite3" <<'PYEOF'
import sqlite3, sys
src = sqlite3.connect('db.sqlite3')
dst = sqlite3.connect(sys.argv[1])
with dst:
    src.backup(dst)          # горячая копия, сайт останавливать не нужно
src.close(); dst.close()
print('копия базы:', sys.argv[1])
PYEOF

echo "=== 2. Состояние до деплоя ==="
git -C "$REPO" rev-parse --short HEAD | tee "$BACKUPS/commit-before-$STAMP.txt"
"$PY" manage.py shell -c "from main_app.models import Book, Facultet, VideoLecture; print('книг', Book.objects.count(), '| факультетов', Facultet.objects.count(), '| видео', VideoLecture.objects.count())" | tee "$BACKUPS/counts-before-$STAMP.txt"

echo "=== 3. Миграция 0008 (её нет в git, иначе pull упадёт) ==="
M008="$APP/main_app/migrations/0008_videolecture.py"
if [ -f "$M008" ] && ! git -C "$REPO" ls-files --error-unmatch \
        "main/main/main_app/migrations/0008_videolecture.py" >/dev/null 2>&1; then
    mv "$M008" "$BACKUPS/0008_videolecture.py.$STAMP"
    echo "отложена в $BACKUPS/0008_videolecture.py.$STAMP"
else
    echo "уже в git или отсутствует — ничего не делаем"
fi

echo "=== 4. Забираем код ==="
git -C "$REPO" pull --ff-only origin main
git -C "$REPO" rev-parse --short HEAD

echo "=== 5. Зависимости ==="
"$PIP" install -r "$APP/requirements.txt"
"$PIP" freeze > "$BACKUPS/pip-freeze-$STAMP.txt"

echo "=== 6. Проверка конфигурации (сайт ещё на старом коде) ==="
"$PY" manage.py check

echo "=== 7. Миграции ==="
"$PY" manage.py migrate --noinput

echo "=== 8. Статика ==="
"$PY" manage.py collectstatic --noinput

echo "=== 9. Перезапуск ==="
date > "$TRIGGER" 2>/dev/null || echo "не удалось записать $TRIGGER"
ok=0
for _ in $(seq 1 15); do
    sleep 2
    if curl -s "http://127.0.0.1:$PORT/" | grep -q "$MARKER"; then
        ok=1; break
    fi
done
if [ "$ok" != 1 ]; then
    echo
    echo "!!! Сайт всё ещё отдаёт старый код — перезапуск не произошёл."
    echo "!!! Попросите администратора выполнить: systemctl restart gunicorn"
    echo "!!! Код, пакеты и миграции уже на месте, нужен только перезапуск."
    exit 2
fi
echo "новый код в работе"

echo "=== 10. Проверка после деплоя ==="
curl -sI "http://127.0.0.1:$PORT/" | head -2
"$PY" manage.py shell -c "from main_app.models import Book, Facultet, VideoLecture, Chapter; print('книг', Book.objects.count(), '| факультетов', Facultet.objects.count(), '| видео', VideoLecture.objects.count(), '| глав', Chapter.objects.count())"
echo "было до деплоя:"; cat "$BACKUPS/counts-before-$STAMP.txt"

echo
echo "ГОТОВО. Проверьте вручную: главная, /admin/, страница книги, /video-lectures/"
echo "Откат: $REPO/rollback.sh"
