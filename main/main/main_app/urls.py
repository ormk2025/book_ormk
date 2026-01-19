from django.urls import path
from . import views

app_name = 'books'

urlpatterns = [
    path('', views.index, name='index'),
    path('all/', views.all_books, name='all_books'),
    path('faculty/<int:facultet_id>/', views.faculty_books, name='faculty_books'),
    path('book/<int:book_id>/', views.book_detail, name='book_detail'),
    path('video-lectures/', views.video_lectures, name='video_lectures'),
]