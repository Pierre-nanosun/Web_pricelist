import csv
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from price_list_app.models import PanelColour, PanelDesign

class Command(BaseCommand):
    help = 'Populate PanelColour and PanelDesign models with unique values from data.csv'

    def handle(self, *args, **kwargs):
        csv_file_path = os.path.join(settings.BASE_DIR, 'data', 'data.csv')

        if not os.path.exists(csv_file_path):
            self.stdout.write(self.style.ERROR(f'{csv_file_path} does not exist'))
            return

        with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            panel_colours = set()
            panel_designs = set()

            for row in reader:
                panel_colours.add(row['panel_colour'])
                panel_designs.add(row['panel_design'])

            # Populate PanelColour
            for colour in panel_colours:
                if colour:
                    PanelColour.objects.get_or_create(name=colour)

            # Populate PanelDesign
            for design in panel_designs:
                if design:
                    PanelDesign.objects.get_or_create(name=design)

        self.stdout.write(self.style.SUCCESS('Successfully populated PanelColour and PanelDesign models'))
