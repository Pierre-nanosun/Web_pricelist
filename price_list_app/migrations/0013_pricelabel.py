# Generated by Django 5.0.6 on 2024-07-02 09:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("price_list_app", "0012_logo"),
    ]

    operations = [
        migrations.CreateModel(
            name="PriceLabel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "product_group",
                    models.CharField(
                        choices=[("Panels", "Panels"), ("Other", "Other")],
                        max_length=20,
                        unique=True,
                    ),
                ),
                ("price_label_1", models.CharField(max_length=100)),
                ("price_label_2", models.CharField(max_length=100)),
                ("price_label_3", models.CharField(max_length=100)),
                ("price_label_4", models.CharField(max_length=100)),
            ],
        ),
    ]
