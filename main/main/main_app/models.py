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

    def __str__(self):
        return self.name

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
    - Ищет index.html (в корне или в mobile/)
    - Сохраняет правильную папку в mobile_folder
    """
    if not created and 'mobile_zip' not in kwargs.get('update_fields', []):
        return

    if instance.mobile_zip:
        extract_path = os.path.join(settings.MEDIA_ROOT, 'books', str(instance.id))

        # Удаляем старую папку
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)

        try:
            os.makedirs(extract_path, exist_ok=True)

            with zipfile.ZipFile(instance.mobile_zip.path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)

            found_folder = None

            # Ищем index.html (приоритетно mobile, потом просто index.html)
            for root, dirs, files in os.walk(extract_path):
                if 'mobile' in dirs:
                    found_folder = os.path.relpath(os.path.join(root, 'mobile'), settings.MEDIA_ROOT)
                    break
                elif 'index.html' in files:
                    found_folder = os.path.relpath(root, settings.MEDIA_ROOT)
                    break

            if found_folder:
                post_save.disconnect(extract_zip_on_save, sender=Book)
                instance.mobile_folder = found_folder
                instance.save(update_fields=['mobile_folder'])
                post_save.connect(extract_zip_on_save, sender=Book)
                print(f"[OK] Книга распакована в: {found_folder}")
            else:
                print("[WARN] Не найден index.html в архиве")

        except Exception as e:
            print(f"[ERROR] Ошибка при распаковке ZIP: {e}")
