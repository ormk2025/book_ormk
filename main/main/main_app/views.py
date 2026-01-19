from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Facultet, Book, VideoLecture


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
    index_html_path = book.get_index_html_path()
    return render(request, 'book_detail.html', {
        'book': book,
        'facultets': facultets,
        'index_html_path': index_html_path
    })




def video_lectures(request):
    
    videos = VideoLecture.objects.all().order_by('-id')

    return render(request, 'video_lectures.html', {
        
        'videos': videos
    })
