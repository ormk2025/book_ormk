from django.shortcuts import render, get_object_or_404
from .models import Facultet, Book
from django.db.models import Q

def index(request):
    facultets = Facultet.objects.all()
    last_books = Book.objects.filter(last_book=True)
    
    search = request.GET.get('q')
    
    if search:
        books = Book.objects.filter(
            Q(name__icontains=search) | Q(author__icontains=search) | Q(year__icontains=search) | Q(specialty_code__icontains=search)  # Добавляем поиск по автору
        )
    else:
        books = last_books  # Если поиска нет, показываем последние книги
    
    return render(request, 'index.html', {'facultets': facultets, 'books': books})

def faculty_books(request, facultet_id):
    facultet = get_object_or_404(Facultet, id=facultet_id)
    books = Book.objects.filter(facultet=facultet)
    return render(request, 'faculty_books.html', {'facultet': facultet, 'books': books})

def book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    index_html_path = book.get_index_html_path()
    print(f"Путь к index.html: {index_html_path}")  # Для отладки
    return render(request, 'book_detail.html', {'book': book, 'index_html_path': index_html_path})