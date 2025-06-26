from django.contrib import admin
from .models import Book, Facultet

@admin.register(Facultet)
class FacultetAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('name', 'author', 'year', 'facultet', 'last_book', 'number')
    fields = ('name', 'author', 'year', 'facultet', 'annotation', 'title_image', 'last_book', 'number', 'mobile_zip','specialty_code')