from django.urls import path
from . import views

app_name = 'books'

urlpatterns = [
    path('', views.index, name='index'),
    path('faculty/<int:facultet_id>/', views.faculty_books, name='faculty_books'),
    path('book/<int:book_id>/', views.book_detail, name='book_detail'),
]