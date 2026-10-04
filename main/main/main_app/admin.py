from django.contrib import admin
from django.utils.html import format_html
from adminsortable2.admin import SortableAdminBase, SortableStackedInline, SortableTabularInline
from django_summernote.admin import SummernoteModelAdmin, SummernoteInlineModelAdmin

from .models import Book, Facultet, VideoLecture, Chapter, BookElement


@admin.register(Facultet)
class FacultetAdmin(admin.ModelAdmin):
    list_display = ('name', 'image_preview')
    search_fields = ('name',)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:40px;border-radius:6px;"/>', obj.image.url
            )
        return "—"
    image_preview.short_description = "Превью"


@admin.register(VideoLecture)
class VideoLectureAdmin(admin.ModelAdmin):
    list_display = ('title', 'video_file')
    search_fields = ('title',)


class ChapterInline(SortableTabularInline):
    model = Chapter
    extra = 1
    fields = ('title', 'order')
    readonly_fields = ()
    show_change_link = True


class BookElementInline(SortableStackedInline, SummernoteInlineModelAdmin):
    model = BookElement
    extra = 1
    fields = ('content', 'order')
    summernote_fields = ('content',)


@admin.register(Book)
class BookAdmin(SortableAdminBase, admin.ModelAdmin):
    list_display = (
        'cover_preview', 'name', 'author', 'year', 'facultet',
        'book_type_badge', 'last_book', 'number',
    )
    list_display_links = ('cover_preview', 'name')
    list_filter = ('facultet', 'last_book', 'year')
    search_fields = ('name', 'author', 'specialty_code', 'year')
    list_per_page = 30
    autocomplete_fields = ('facultet',)
    inlines = [ChapterInline]

    fieldsets = (
        ("Основное", {
            'fields': ('name', 'author', 'year', 'facultet', 'specialty_code', 'number', 'last_book'),
        }),
        ("Обложка и аннотация", {
            'fields': ('title_image', 'annotation'),
        }),
        ("Веб-книга (создаётся на сайте)", {
            'classes': ('collapse',),
            'fields': ('description',),
            'description': "Если заполнить главы ниже — книга станет веб-книгой. Иначе используется ZIP-файл.",
        }),
        ("ZIP-книга (старый формат)", {
            'classes': ('collapse',),
            'fields': ('mobile_zip', 'mobile_folder'),
            'description': "Загрузите ZIP-архив — он автоматически распакуется.",
        }),
    )
    readonly_fields = ('mobile_folder',)

    def cover_preview(self, obj):
        if obj.title_image:
            return format_html(
                '<img src="{}" style="height:50px;width:40px;object-fit:cover;border-radius:4px;"/>',
                obj.title_image.url,
            )
        return "—"
    cover_preview.short_description = "Обложка"

    def book_type_badge(self, obj):
        if obj.is_web_book:
            return format_html(
                '<span style="background:#28a745;color:#fff;padding:3px 8px;border-radius:10px;font-size:11px;">🌐 Веб</span>'
            )
        if obj.is_zip_book:
            return format_html(
                '<span style="background:#007bff;color:#fff;padding:3px 8px;border-radius:10px;font-size:11px;">📦 ZIP</span>'
            )
        return format_html(
            '<span style="background:#6c757d;color:#fff;padding:3px 8px;border-radius:10px;font-size:11px;">—</span>'
        )
    book_type_badge.short_description = "Тип"


@admin.register(Chapter)
class ChapterAdmin(SortableAdminBase, admin.ModelAdmin):
    list_display = ('title', 'book', 'order', 'elements_count')
    list_filter = ('book',)
    search_fields = ('title', 'book__name')
    autocomplete_fields = ('book',)
    inlines = [BookElementInline]

    def elements_count(self, obj):
        return obj.elements.count()
    elements_count.short_description = "Блоков"
