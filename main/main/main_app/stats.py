"""Счётчики посетителей сайта и читателей книг."""
import re
from datetime import datetime, time, timedelta

from django.db import DatabaseError
from django.db.models import F, Sum
from django.utils import timezone

from .models import Book, DailyVisits

BOT_RE = re.compile(
    r'bot|crawl|spider|slurp|preview|headless|curl|wget|python|scrapy|httpclient|monitor',
    re.IGNORECASE,
)


def is_countable(request):
    """Роботы и предзагрузка страниц браузером не считаются."""
    agent = request.META.get('HTTP_USER_AGENT', '')
    purpose = request.META.get('HTTP_SEC_PURPOSE', '') + request.META.get('HTTP_PURPOSE', '')
    return bool(agent) and not BOT_RE.search(agent) and 'prefetch' not in purpose


def set_day_cookie(response, name, path='/'):
    """Cookie до полуночи: по ней один браузер учитывается один раз в день."""
    now = timezone.localtime()
    midnight = timezone.make_aware(datetime.combine(now.date() + timedelta(days=1), time.min))
    response.set_cookie(
        name, '1', max_age=max(1, int((midnight - now).total_seconds())),
        path=path, httponly=True, samesite='Lax',
    )


def count_visit():
    today = timezone.localdate()
    DailyVisits.objects.get_or_create(date=today)
    DailyVisits.objects.filter(date=today).update(visitors=F('visitors') + 1)


def visit_totals():
    today = DailyVisits.objects.filter(date=timezone.localdate()).first()
    return {
        'today': today.visitors if today else 0,
        'total': DailyVisits.objects.aggregate(total=Sum('visitors'))['total'] or 0,
    }


def count_reader(request, response, book, path):
    """Учитывает читателя книги. Ошибка счётчика не должна мешать чтению."""
    name = f'read_{book.pk}'
    if name in request.COOKIES or not is_countable(request):
        return
    try:
        Book.objects.filter(pk=book.pk).update(readers=F('readers') + 1)
    except DatabaseError:
        return
    set_day_cookie(response, name, path)
