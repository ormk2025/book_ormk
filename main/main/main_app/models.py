from django.core.validators import FileExtensionValidator
from django.db import models
import logging
import os
import shutil
import tempfile
import zipfile
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.conf import settings

logger = logging.getLogger(__name__)


class Facultet(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='upload/', blank=True, null=True)

    def __str__(self):
        return self.name


class Book(models.Model):
    name = models.CharField(max_length=300)
    author = models.CharField(max_length=300)
    year = models.IntegerField()
    facultet = models.ForeignKey(Facultet, on_delete=models.CASCADE)
    annotation = models.TextField()
    title_image = models.ImageField(upload_to='upload/', blank=True, null=True)
    last_book = models.BooleanField(default=False)
    number = models.IntegerField()
    mobile_zip = models.FileField(
        upload_to='books/zips/',
        verbose_name="ZIP-файл книги",
        blank=True,
        null=True
    )
    mobile_folder = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Папка с HTML книгой"
    )
    specialty_code = models.CharField(max_length=300, null=True, blank=True)

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Описание (для веб-книги)",
        help_text="Используется только для книг, создаваемых прямо на сайте."
    )

    def __str__(self):
        return self.name

    @property
    def is_web_book(self):
        return self.chapters.exists()

    @property
    def is_zip_book(self):
        return bool(self.mobile_zip) and not self.is_web_book

    def get_index_html_path(self):
        """Возвращает URL к index.html — ищет и в корне, и внутри подпапок"""
        if self.mobile_folder:
            abs_path = os.path.join(settings.MEDIA_ROOT, self.mobile_folder)

            # Проверяем index.html в корне
            index_path = os.path.join(abs_path, 'index.html')
            if os.path.exists(index_path):
                relative_path = os.path.relpath(index_path, settings.MEDIA_ROOT)
                return f"{settings.MEDIA_URL}{relative_path}"

            # Если нет — ищем глубже
            for root, dirs, files in os.walk(abs_path):
                if 'index.html' in files:
                    relative_path = os.path.relpath(
                        os.path.join(root, 'index.html'),
                        settings.MEDIA_ROOT
                    )
                    return f"{settings.MEDIA_URL}{relative_path}"

        return None

def extract_book_zip(book):
    """
    Распаковывает архив книги в media/books/{id}/ и сохраняет путь к папке с index.html.

    Архив сначала распаковывается во временную папку, поэтому битый архив или
    архив без index.html не затрагивает уже опубликованную версию книги.
    """
    books_root = os.path.join(settings.MEDIA_ROOT, 'books')
    os.makedirs(books_root, exist_ok=True)
    temp_path = tempfile.mkdtemp(prefix=f'.extract_{book.pk}_', dir=books_root)

    try:
        with zipfile.ZipFile(book.mobile_zip.path, 'r') as zip_ref:
            zip_ref.extractall(temp_path)

        index_folder = next(
            (root for root, dirs, files in os.walk(temp_path) if 'index.html' in files),
            None,
        )
        if index_folder is None:
            logger.warning("Книга %s: в архиве не найден index.html", book.pk)
            return

        folder = os.path.normpath(
            os.path.join('books', str(book.pk), os.path.relpath(index_folder, temp_path))
        )
        final_path = os.path.join(books_root, str(book.pk))
        if os.path.exists(final_path):
            shutil.rmtree(final_path)
        os.chmod(temp_path, 0o755)  # mkdtemp создаёт папку 0700, веб-сервер её не прочитает
        os.replace(temp_path, final_path)

        Book.objects.filter(pk=book.pk).update(mobile_folder=folder)
        book.mobile_folder = folder
    except (OSError, zipfile.BadZipFile) as e:
        logger.error("Книга %s: ошибка при распаковке ZIP: %s", book.pk, e)
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


@receiver(pre_save, sender=Book)
def remember_previous_zip(sender, instance, **kwargs):
    """Запоминает архив из базы, чтобы после сохранения понять, заменили ли его."""
    instance._previous_zip = (
        Book.objects.filter(pk=instance.pk).values_list('mobile_zip', flat=True).first()
        if instance.pk else None
    )


@receiver(post_save, sender=Book)
def extract_zip_on_save(sender, instance, raw=False, **kwargs):
    """Распаковывает архив, если он новый или папки с книгой нет на диске."""
    if raw or not instance.mobile_zip:
        return

    zip_changed = instance.mobile_zip.name != getattr(instance, '_previous_zip', None)
    folder_missing = not instance.mobile_folder or not os.path.isdir(
        os.path.join(settings.MEDIA_ROOT, instance.mobile_folder)
    )
    if zip_changed or folder_missing:
        extract_book_zip(instance)



class Chapter(models.Model):
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="chapters",
        verbose_name="Книга",
    )
    title = models.CharField(max_length=255, verbose_name="Название главы")
    order = models.PositiveIntegerField(default=0, db_index=True, verbose_name="Порядок")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Глава"
        verbose_name_plural = "Главы"

    def __str__(self):
        return f"{self.book.name} — {self.title}"


class BookElement(models.Model):
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name="elements",
        verbose_name="Глава",
    )
    content = models.TextField(verbose_name="Контент", blank=True, default="")
    order = models.PositiveIntegerField(default=0, db_index=True, verbose_name="Порядок")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Блок контента"
        verbose_name_plural = "Блоки контента"

    def __str__(self):
        return f"{self.chapter.title} — блок {self.order}"


class VideoLecture(models.Model):
    title = models.CharField(max_length=300)
    video_file = models.FileField(upload_to='video_lectures/')
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.title


class VirtualLab(models.Model):
    title = models.CharField(max_length=300, verbose_name="Тема")
    description = models.TextField(blank=True, default="", verbose_name="Описание")
    cover = models.ImageField(
        upload_to='virtual_labs/covers/', blank=True, null=True, verbose_name="Обложка"
    )
    html_file = models.FileField(
        upload_to='virtual_labs/',
        validators=[FileExtensionValidator(['html', 'htm'])],
        verbose_name="HTML-файл",
        help_text="Один самодостаточный HTML-файл: стили и скрипты внутри него или по ссылкам из интернета.",
    )
    is_published = models.BooleanField(default=True, verbose_name="Показывать на сайте")
    order = models.PositiveIntegerField(default=0, db_index=True, verbose_name="Порядок")

    class Meta:
        ordering = ["order", "-id"]
        verbose_name = "3D-виртуалка"
        verbose_name_plural = "3D-виртуалки (бета)"

    def __str__(self):
        return self.title
