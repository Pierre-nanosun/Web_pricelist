# Generated by Django 5.0.6 on 2024-07-12 14:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("price_list_app", "0010_panelcolour_paneldesign"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuration",
            name="selected_columns",
            field=models.JSONField(default=list),
        ),
    ]
