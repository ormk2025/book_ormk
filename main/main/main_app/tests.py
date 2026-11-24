import io
import os
import re
import shutil
import tempfile
import zipfile
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import unquote

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Book, BookElement, Chapter, DailyVisits, Facultet, VideoLecture, VirtualLab


def make_zip(files, name='book.zip'):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='application/zip')


class MediaTestCase(TestCase):
    def setUp(self):
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root)
        override = override_settings(MEDIA_ROOT=media_root)
        override.enable()
        self.addCleanup(override.disable)
        self.media_root = media_root
        self.facultet = Facultet.objects.create(name='Факультет')

    def create_book(self, **kwargs):
        return Book.objects.create(
            name='Книга', author='Автор', year=2026, annotation='Аннотация',
            number=1, facultet=self.facultet, **kwargs,
        )

    def read_index(self, book):
        book.refresh_from_db()
        path = os.path.join(self.media_root, book.mobile_folder, 'index.html')
        with open(path, encoding='utf-8') as index:
            return index.read()


class ZipExtractionTests(MediaTestCase):
    def test_new_book_with_zip_is_extracted(self):
        book = self.create_book(mobile_zip=make_zip({'index.html': 'версия 1'}))
        self.assertEqual(self.read_index(book), 'версия 1')
        self.assertEqual(book.mobile_folder, f'books/{book.pk}')

    def test_index_in_subfolder_is_found(self):
        book = self.create_book(mobile_zip=make_zip({'inner/index.html': 'версия 1'}))
        self.assertEqual(self.read_index(book), 'версия 1')
        self.assertEqual(book.mobile_folder, f'books/{book.pk}/inner')

    def test_zip_added_to_existing_book_is_extracted(self):
        book = self.create_book()
        book.mobile_zip = make_zip({'index.html': 'версия 1'})
        book.save()
        self.assertEqual(self.read_index(book), 'версия 1')

    def test_replaced_zip_shows_new_version(self):
        book = self.create_book(mobile_zip=make_zip({'index.html': 'версия 1', 'old.txt': 'x'}))
        book = Book.objects.get(pk=book.pk)
        book.mobile_zip = make_zip({'index.html': 'версия 2'})
        book.save()
        self.assertEqual(self.read_index(book), 'версия 2')
        self.assertFalse(os.path.exists(os.path.join(self.media_root, book.mobile_folder, 'old.txt')))

    def test_unrelated_save_does_not_extract_again(self):
        book = self.create_book(mobile_zip=make_zip({'index.html': 'версия 1'}))
        book = Book.objects.get(pk=book.pk)
        marker = os.path.join(self.media_root, book.mobile_folder, 'marker.txt')
        open(marker, 'w').close()
        book.name = 'Новое название'
        book.save()
        self.assertTrue(os.path.exists(marker))

    def test_missing_folder_is_restored_on_save(self):
        book = self.create_book(mobile_zip=make_zip({'index.html': 'версия 1'}))
        book = Book.objects.get(pk=book.pk)
        shutil.rmtree(os.path.join(self.media_root, book.mobile_folder))
        book.save()
        self.assertEqual(self.read_index(book), 'версия 1')

    def test_broken_zip_keeps_published_version(self):
        book = self.create_book(mobile_zip=make_zip({'index.html': 'версия 1'}))
        book = Book.objects.get(pk=book.pk)
        book.mobile_zip = SimpleUploadedFile('broken.zip', b'not a zip')
        with self.assertLogs('main_app.models', level='ERROR'):
            book.save()
        self.assertEqual(self.read_index(book), 'версия 1')

    def test_zip_without_index_keeps_published_version(self):
        book = self.create_book(mobile_zip=make_zip({'index.html': 'версия 1'}))
        book = Book.objects.get(pk=book.pk)
        book.mobile_zip = make_zip({'readme.txt': 'нет index'})
        with self.assertLogs('main_app.models', level='WARNING'):
            book.save()
        self.assertEqual(self.read_index(book), 'версия 1')

    def test_no_temp_folders_left_behind(self):
        self.create_book(mobile_zip=make_zip({'index.html': 'версия 1'}))
        leftovers = [
            name for name in os.listdir(os.path.join(self.media_root, 'books'))
            if name.startswith('.extract_')
        ]
        self.assertEqual(leftovers, [])


class PageTests(MediaTestCase):
    def test_public_pages(self):
        zip_book = self.create_book(mobile_zip=make_zip({'index.html': 'книга'}))
        web_book = self.create_book()
        chapter = Chapter.objects.create(book=web_book, title='Глава 1')
        BookElement.objects.create(chapter=chapter, content='<p>Текст главы</p>')
        VideoLecture.objects.create(title='Лекция', video_file='video_lectures/a.mp4')

        for url, expected in [
            (reverse('books:index'), 'hero-badge'),
            (reverse('books:index') + '?q=Книга', 'Книга'),
            (reverse('books:all_books'), 'Книга'),
            (reverse('books:faculty_books', args=[self.facultet.pk]), 'Книга'),
            (reverse('books:book_detail', args=[zip_book.pk]), reverse('books:read_book', args=[zip_book.pk])),
            (reverse('books:book_detail', args=[web_book.pk]), 'Глава 1'),
            (reverse('books:chapter_detail', args=[chapter.pk]), 'Текст главы'),
            (reverse('books:video_lectures'), 'Лекция'),
        ]:
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), expected)


class VirtualLabTests(MediaTestCase):
    def create_lab(self, **kwargs):
        return VirtualLab.objects.create(
            title='Качество муки',
            html_file=SimpleUploadedFile('Виртуальная лаборатория.html', b'<h1>lab</h1>'),
            **kwargs,
        )

    def test_list_and_player(self):
        lab = self.create_lab(description='Шесть опытов')
        url = reverse('books:virtual_lab_detail', args=[lab.pk])
        page = self.client.get(reverse('books:virtual_labs'))
        self.assertContains(page, 'Качество муки')
        self.assertContains(page, url)
        self.assertContains(self.client.get(url), f'src="{lab.html_file.url}"')

    def test_player_iframe_is_isolated_from_site(self):
        html = self.client.get(
            reverse('books:virtual_lab_detail', args=[self.create_lab().pk])
        ).content.decode()
        sandbox = re.search(r'sandbox="([^"]*)"', html).group(1).split()
        self.assertIn('allow-scripts', sandbox)
        self.assertNotIn('allow-same-origin', sandbox)

    def test_unpublished_lab_is_hidden(self):
        lab = self.create_lab(is_published=False)
        self.assertNotContains(self.client.get(reverse('books:virtual_labs')), 'Качество муки')
        response = self.client.get(reverse('books:virtual_lab_detail', args=[lab.pk]))
        self.assertEqual(response.status_code, 404)

    def test_every_page_links_to_section(self):
        book = self.create_book()
        web_book = self.create_book()
        chapter = Chapter.objects.create(book=web_book, title='Глава 1')
        for url in [
            reverse('books:index'), reverse('books:all_books'), reverse('books:video_lectures'),
            reverse('books:faculty_books', args=[self.facultet.pk]),
            reverse('books:book_detail', args=[book.pk]),
            reverse('books:book_detail', args=[web_book.pk]),
            reverse('books:chapter_detail', args=[chapter.pk]),
        ]:
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), reverse('books:virtual_labs'))


BROWSER = {'HTTP_USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0) Chrome/130.0'}


class StatsTests(MediaTestCase):
    def setUp(self):
        super().setUp()
        self.visit_url = reverse('books:visit')

    def test_browser_counted_once_a_day(self):
        self.assertEqual(self.client.post(self.visit_url, **BROWSER).json(), {'today': 1, 'total': 1})
        self.assertEqual(self.client.post(self.visit_url, **BROWSER).json(), {'today': 1, 'total': 1})
        other = self.client_class()
        self.assertEqual(other.post(self.visit_url, **BROWSER).json(), {'today': 2, 'total': 2})

    def test_total_includes_previous_days(self):
        DailyVisits.objects.create(date=timezone.localdate() - timedelta(days=1), visitors=10)
        self.assertEqual(self.client.post(self.visit_url, **BROWSER).json(), {'today': 1, 'total': 11})

    def test_bots_are_not_counted(self):
        for agent in ['Googlebot/2.1', 'curl/8.0', '']:
            response = self.client.post(self.visit_url, HTTP_USER_AGENT=agent)
            self.assertEqual(response.json(), {'today': 0, 'total': 0})

    def test_visit_needs_no_csrf_token_and_only_post(self):
        strict = self.client_class(enforce_csrf_checks=True)
        self.assertEqual(strict.post(self.visit_url, **BROWSER).status_code, 200)
        self.assertEqual(self.client.get(self.visit_url, **BROWSER).status_code, 405)

    def test_zip_book_readers(self):
        book = self.create_book(mobile_zip=make_zip({'глава/index.html': 'книга'}))
        url = reverse('books:read_book', args=[book.pk])
        response = self.client.get(url, **BROWSER)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(unquote(response['Location']), f'/media/books/{book.pk}/глава/index.html')
        self.client.get(url, **BROWSER)
        self.client_class().get(url, HTTP_USER_AGENT='Googlebot/2.1')
        self.client_class().get(url, **BROWSER)
        book.refresh_from_db()
        self.assertEqual(book.readers, 2)
        self.assertContains(self.client.get(reverse('books:book_detail', args=[book.pk])), 'Читателей:</strong> 2')

    def test_reading_one_book_does_not_block_another(self):
        books = [self.create_book(mobile_zip=make_zip({'index.html': 'x'})) for _ in range(2)]
        for book in books:
            self.client.get(reverse('books:read_book', args=[book.pk]), **BROWSER)
            book.refresh_from_db()
            self.assertEqual(book.readers, 1)

    def test_web_book_counts_reader_once_for_all_chapters(self):
        book = self.create_book()
        for number in (1, 2):
            chapter = Chapter.objects.create(book=book, title=f'Глава {number}')
            self.client.get(reverse('books:chapter_detail', args=[chapter.pk]), **BROWSER)
        book.refresh_from_db()
        self.assertEqual(book.readers, 1)

    def test_book_without_file(self):
        url = reverse('books:read_book', args=[self.create_book().pk])
        self.assertEqual(self.client.get(url, **BROWSER).status_code, 404)

    def test_counter_failure_does_not_block_reading(self):
        book = self.create_book(mobile_zip=make_zip({'index.html': 'x'}))
        with patch('main_app.stats.Book.objects.filter', side_effect=OperationalError('locked')):
            response = self.client.get(reverse('books:read_book', args=[book.pk]), **BROWSER)
        self.assertEqual(response.status_code, 302)


class AdminTests(MediaTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(
            get_user_model().objects.create_superuser('admin', 'admin@example.com', 'password')
        )

    def test_admin_pages_open(self):
        book = self.create_book()
        chapter = Chapter.objects.create(book=book, title='Глава 1')
        for url in [
            reverse('admin:index'),
            reverse('admin:main_app_book_changelist'),
            reverse('admin:main_app_book_add'),
            reverse('admin:main_app_dailyvisits_changelist'),
            reverse('admin:main_app_book_change', args=[book.pk]),
            reverse('admin:main_app_chapter_change', args=[chapter.pk]),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_replacing_zip_through_admin_form(self):
        book = self.create_book(mobile_zip=make_zip({'index.html': 'версия 1'}))
        form = self.client.get(reverse('admin:main_app_book_change', args=[book.pk])).context['adminform'].form
        data = {
            'name': book.name, 'author': book.author, 'year': book.year,
            'facultet': book.facultet_id, 'number': book.number, 'annotation': book.annotation,
            'mobile_zip': make_zip({'index.html': 'версия 2'}),
            'chapters-TOTAL_FORMS': 0, 'chapters-INITIAL_FORMS': 0,
            'chapters-MIN_NUM_FORMS': 0, 'chapters-MAX_NUM_FORMS': 1000,
        }
        self.assertIn('mobile_zip', form.fields)
        response = self.client.post(reverse('admin:main_app_book_change', args=[book.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.read_index(book), 'версия 2')

    def test_virtual_lab_accepts_only_html(self):
        url = reverse('admin:main_app_virtuallab_add')
        self.assertEqual(self.client.get(url).status_code, 200)
        data = {'title': 'Тема', 'order': 0, 'is_published': 'on'}
        self.client.post(url, {**data, 'html_file': SimpleUploadedFile('lab.exe', b'x')})
        self.assertEqual(VirtualLab.objects.count(), 0)
        self.client.post(url, {**data, 'html_file': SimpleUploadedFile('lab.html', b'<p>x</p>')})
        self.assertEqual(VirtualLab.objects.count(), 1)
        self.assertContains(self.client.get(reverse('admin:main_app_virtuallab_changelist')), 'Открыть')

    def test_anonymous_cannot_upload_summernote_attachment(self):
        self.client.logout()
        response = self.client.post(
            '/summernote/upload_attachment/',
            {'files': SimpleUploadedFile('a.png', b'x', content_type='image/png')},
        )
        self.assertNotEqual(response.status_code, 200)
