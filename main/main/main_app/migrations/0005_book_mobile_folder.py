# Generated by Django 5.2.1 on 2025-06-19 07:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0004_remove_book_mobile_folder_book_mobile_zip'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='mobile_folder',
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name='Путь к папке mobile'),
        ),
    ]
