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

    # 📖 Возвращает путь к index.html
    def get_index_html_path(self):
        if self.mobile_folder:
            index_path = os.path.join(settings.MEDIA_ROOT, self.mobile_folder, 'index.html')
            if os.path.exists(index_path):
                # Возвращаем URL для браузера
                return f"{settings.MEDIA_URL}{self.mobile_folder}/index.html"
        return None


# 🧩 Автоматическая распаковка книги после сохранения
@receiver(post_save, sender=Book)
def extract_zip_on_save(sender, instance, created, **kwargs):
    """
    После загрузки ZIP-файла:
    1. Удаляет старую папку книги, если она есть.
    2. Распаковывает архив в media/books/{id}/
    3. Ищет папку 'mobile' и сохраняет относительный путь в mobile_folder.
    """
    if not created and 'mobile_zip' not in kwargs.get('update_fields', []):
        return

    if instance.mobile_zip:
        extract_path = os.path.join(settings.MEDIA_ROOT, 'books', str(instance.id))

        # 🧹 Удаляем старую папку книги, если она существует
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)

        try:
            os.makedirs(extract_path, exist_ok=True)

            # 📦 Распаковка архива
            with zipfile.ZipFile(instance.mobile_zip.path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)

            # 🔍 Ищем папку 'mobile'
            for root, dirs, files in os.walk(extract_path):
                if 'mobile' in dirs:
                    # Сохраняем относительный путь (от MEDIA_ROOT)
                    mobile_folder = os.path.relpath(os.path.join(root, 'mobile'), settings.MEDIA_ROOT)
                    instance.mobile_folder = mobile_folder
                    instance.save(update_fields=['mobile_folder'])
                    print(f"[OK] Книга распакована в: {mobile_folder}")
                    break
            else:
                print("[WARN] В архиве не найдена папка 'mobile'.")

        except Exception as e:
            print(f"[ERROR] Ошибка при распаковке ZIP: {e}")

