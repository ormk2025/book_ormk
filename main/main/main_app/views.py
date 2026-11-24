from django.db import DatabaseError
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.utils.encoding import iri_to_uri
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Q
from . import stats
from .models import Facultet, Book, VideoLecture, Chapter, VirtualLab


def index(request):
    facultets = Facultet.objects.all()
    last_books = Book.objects.filter(last_book=True)
    total_books = Book.objects.count()
    
    search = request.GET.get('q')
    
    if search:
        books = Book.objects.filter(
            Q(name__icontains=search) | 
            Q(author__icontains=search) | 
            Q(year__icontains=search) | 
            Q(specialty_code__icontains=search)
        )
    else:
        books = last_books
    
    return render(request, 'index.html', {
        'facultets': facultets,
        'books': books,
        'total_books': total_books,
        'search': search
    })


def all_books(request):
    facultets = Facultet.objects.all()
    books = Book.objects.all().order_by('name')
    total_books = books.count()
    return render(request, 'all_books.html', {
        'facultets': facultets,
        'books': books,
        'total_books': total_books
    })


def faculty_books(request, facultet_id):
    facultet = get_object_or_404(Facultet, id=facultet_id)
    books = Book.objects.filter(facultet=facultet)
    facultets = Facultet.objects.all()
    return render(request, 'faculty_books.html', {
        'facultets': facultets,
        'facultet': facultet,
        'books': books
    })


def book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    facultets = Facultet.objects.all()

    if book.is_web_book:
        chapters = book.chapters.all()
        return render(request, 'book_detail_web.html', {
            'book': book,
            'facultets': facultets,
            'chapters': chapters,
        })

    index_html_path = book.get_index_html_path()
    return render(request, 'book_detail.html', {
        'book': book,
        'facultets': facultets,
        'index_html_path': index_html_path
    })


def chapter_detail(request, chapter_id):
    chapter = get_object_or_404(Chapter, id=chapter_id)
    book = chapter.book
    facultets = Facultet.objects.all()
    chapters = book.chapters.all()
    elements = chapter.elements.all()
    chapter_ids = list(chapters.values_list('id', flat=True))
    idx = chapter_ids.index(chapter.id)
    prev_chapter = chapters[idx - 1] if idx > 0 else None
    next_chapter = chapters[idx + 1] if idx + 1 < len(chapter_ids) else None
    response = render(request, 'chapter_detail.html', {
        'book': book,
        'chapter': chapter,
        'chapters': chapters,
        'elements': elements,
        'facultets': facultets,
        'prev_chapter': prev_chapter,
        'next_chapter': next_chapter,
    })
    stats.count_reader(request, response, book, path='/chapter/')
    return response




def video_lectures(request):
    
    videos = VideoLecture.objects.all().order_by('-id')

    return render(request, 'video_lectures.html', {
        
        'videos': videos
    })


def virtual_labs(request):
    return render(request, 'virtual_labs.html', {
        'facultets': Facultet.objects.all(),
        'labs': VirtualLab.objects.filter(is_published=True),
    })


def virtual_lab_detail(request, lab_id):
    lab = get_object_or_404(VirtualLab, id=lab_id, is_published=True)
    return render(request, 'virtual_lab_detail.html', {'lab': lab})


@never_cache
@require_GET
def read_book(request, book_id):
    """Считает читателя и открывает файл ZIP-книги."""
    book = get_object_or_404(Book, id=book_id)
    index_html_path = book.get_index_html_path()
    if not index_html_path:
        raise Http404
    response = redirect(iri_to_uri(index_html_path))
    stats.count_reader(request, response, book, path=request.path)
    return response


# Без CSRF-токена: запрос только увеличивает счётчик и не использует права пользователя
@csrf_exempt
@never_cache
@require_POST
def visit(request):
    try:
        counted = 'visited' not in request.COOKIES and stats.is_countable(request)
        if counted:
            stats.count_visit()
        response = JsonResponse(stats.visit_totals())
    except DatabaseError:
        return JsonResponse({}, status=503)
    if counted:
        stats.set_day_cookie(response, 'visited')
    return response
