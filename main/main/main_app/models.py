from django.db import models
import os
import zipfile
from django.db.models.signals import post_save
from django.dispatch import receiver

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
    mobile_zip = models.FileField(upload_to='books/zips/', verbose_name="ZIP-файл с мобильной версией", blank=True, null=True)
    mobile_folder = models.CharField(max_length=500, blank=True, null=True, verbose_name="Путь к папке mobile")
    specialty_code = models.CharField(max_length=300, null=True, blank=True)

    def __str__(self):
        return self.name

    def get_index_html_path(self):
        # Возвращает путь к index.html внутри папки mobile
        if self.mobile_folder and os.path.exists(self.mobile_folder):
            index_path = os.path.join(self.mobile_folder, 'index.html')
            if os.path.exists(index_path):
                # Возвращаем абсолютный URL для медиа
                relative_path = os.path.relpath(index_path, os.path.join('media', ''))
                return f"/media/{relative_path}"
        return None

@receiver(post_save, sender=Book)
def extract_zip_on_save(sender, instance, created, **kwargs):
    if created and instance.mobile_zip:
        print(f"Обработка ZIP: {instance.mobile_zip.path}")
        extract_path = os.path.join('media', 'books', str(instance.id))
        try:
            os.makedirs(extract_path, exist_ok=True)
            with zipfile.ZipFile(instance.mobile_zip.path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            for root, dirs, files in os.walk(extract_path):
                print(f"Проверка директории: {root}, папки: {dirs}")
                if 'mobile' in dirs:
                    mobile_folder = os.path.join(root, 'mobile')
                    print(f"Найдена папка mobile: {mobile_folder}")
                    instance.mobile_folder = mobile_folder
                    instance.save(update_fields=['mobile_folder'])
                    break
        except Exception as e:
            print(f"Ошибка при обработке ZIP: {e}")

# Подключение сигнала
post_save.connect(extract_zip_on_save, sender=Book)