from django.urls import path
from . import views

app_name = 'books'

urlpatterns = [
    path('', views.index, name='index'),
    path('all/', views.all_books, name='all_books'),
    path('faculty/<int:facultet_id>/', views.faculty_books, name='faculty_books'),
    path('book/<int:book_id>/', views.book_detail, name='book_detail'),
    path('book/<int:book_id>/read/', views.read_book, name='read_book'),
    path('stats/visit/', views.visit, name='visit'),
    path('chapter/<int:chapter_id>/', views.chapter_detail, name='chapter_detail'),
    path('video-lectures/', views.video_lectures, name='video_lectures'),
    path('virtual-labs/', views.virtual_labs, name='virtual_labs'),
    path('virtual-labs/<int:lab_id>/', views.virtual_lab_detail, name='virtual_lab_detail'),
]