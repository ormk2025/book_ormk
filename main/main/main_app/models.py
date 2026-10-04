from django.db import models
import os
import shutil
import zipfile
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings


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

@receiver(post_save, sender=Book)
def extract_zip_on_save(sender, instance, created, **kwargs):
    """
    После загрузки ZIP:
    - Распаковывает в media/books/{id}/
    - Автоматически ищет index.html
    - Сохраняет путь до папки, где он найден
    """
    if not created and 'mobile_zip' not in (kwargs.get('update_fields') or []):
        return

    if instance.mobile_zip:
        extract_path = os.path.join(settings.MEDIA_ROOT, 'books', str(instance.id))

        # 🧹 Удаляем старую папку книги, если она уже есть
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)

        try:
            os.makedirs(extract_path, exist_ok=True)

            # 📦 Распаковываем архив
            with zipfile.ZipFile(instance.mobile_zip.path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)

            found_folder = None

            # 🔍 Ищем, где находится index.html
            for root, dirs, files in os.walk(extract_path):
                if 'index.html' in files:
                    found_folder = os.path.relpath(root, settings.MEDIA_ROOT)
                    break

            if found_folder:
                # 🚫 Избегаем рекурсии при сохранении
                post_save.disconnect(extract_zip_on_save, sender=Book)
                instance.mobile_folder = found_folder
                instance.save(update_fields=['mobile_folder'])
                post_save.connect(extract_zip_on_save, sender=Book)
                print(f"[OK] Книга распакована в: {found_folder}")
            else:
                print("[WARN] Не найден index.html в архиве")

        except Exception as e:
            print(f"[ERROR] Ошибка при распаковке ZIP: {e}")




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