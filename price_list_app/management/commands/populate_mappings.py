import os
import django
import pandas as pd
from django.core.management.base import BaseCommand
from price_list_app.models import NomenclatureMapping, PanelMapping, Brand
from django.conf import settings

# Ensure the settings module is set
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'price_list_project.settings')
django.setup()

class Command(BaseCommand):
    help = 'Populates the database with initial nomenclature, panel mappings, and brands from data.csv'

    def handle(self, *args, **kwargs):
        # Populating NomenclatureMapping
        nomenclature_data = [
            ('PAN', 'Panels'),
            ('INV', 'Inverters'),
            ('BAT', 'Batteries'),
            ('EVC', 'EV Chargers'),
            ('ACC', 'Accessories'),
            ('CON', 'Constructions'),
            ('PPS', 'Portable Power Station'),
            ('ARC', 'Air Conditions'),
            ('HEP', 'Heat Pumps'),
            ('SMF', 'SmartFlowers'),
            ('CAB', 'Cables')
        ]

        for key, value in nomenclature_data:
            NomenclatureMapping.objects.get_or_create(key=key, value=value)

        # Populating PanelMapping
        panel_data = [
            ('GLASS', 'Glass foil'),
            ('2GLASS', 'Double glass'),
            ('BIF', 'Bifacial'),
            ('FLEXIBLE', 'Flexible'),
            ('GRID', 'Grid feed-in'),
            ('HYBRID', 'Hybrid'),
            ('3PH', 'Triple phase'),
            ('1PH', 'Single phase'),
            ('BF', 'Black Frame'),
            ('FB', 'Full Black'),
            ('FF_ANTHRACITE', 'Frameless Full Anthracite (G001)'),
            ('FF_BLACK', 'Frameless Full Black (B001)'),
            ('FF_BLUE', 'Frameless Full Blue (7003)'),
            ('FF_BRONZE', 'Frameless Full Bronze (3001)'),
            ('FF_DARK_BLUE', 'Frameless Full Dark blue (7002)'),
            ('FF_GOLD', 'Frameless Full Gold (3002)'),
            ('FF_GREEN', 'Frameless Full Green (4002)'),
            ('FF_GREY', 'Frameless Full Grey (G002)'),
            ('FF_LIGHT_BLUE', 'Frameless Full Light blue (7004)'),
            ('FF_LIGHT_GREEN', 'Frameless Full Light green (4001)'),
            ('FF_LIGHT_GREY', 'Frameless Full Light grey (G004)'),
            ('SF', 'Silver Frame')
        ]

        for key, value in panel_data:
            PanelMapping.objects.get_or_create(key=key, value=value)

        # Populating Brand table from data.csv
        csv_file_path = os.path.join(settings.BASE_DIR, 'data', 'data.csv')
        df = pd.read_csv(csv_file_path)
        distinct_brands = df['brand'].dropna().unique()

        for brand in distinct_brands:
            Brand.objects.get_or_create(name=brand)

        self.stdout.write(self.style.SUCCESS('Successfully populated mappings and brands'))
