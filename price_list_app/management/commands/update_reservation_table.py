from django.core.management.base import BaseCommand
from django.db import connection
import pandas as pd
import json
import os
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Update the Reservation_Table using a DataFrame'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the temporary file containing JSON-encoded data for the DataFrame')

    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']
        try:
            if not os.path.exists(file_path):
                error_message = f"File not found: {file_path}"
                self.stdout.write(self.style.ERROR(error_message))
                logger.error(error_message)
                return

            try:
                df = pd.read_json(file_path)
            except ValueError as e:
                error_message = f"Invalid JSON data: {e}"
                self.stdout.write(self.style.ERROR(error_message))
                logger.error(error_message)
                return

            # Validate data
            required_columns = [
                'product_name', 'status', 'bp_eur', 'bp_eur_cz', 'delivery_month', 'available',
                'available_cz', 'released_rtd', 'brand', 'panel_colour', 'panel_design',
                'panel_power', 'inverter_power', 'nomenclature_group', 'delivery_cw', 'length',
                'height', 'width', 'pcs_ctn', 'pcs_pal'
            ]
            for column in required_columns:
                if column not in df.columns:
                    error_message = f'Missing required column: {column}'
                    self.stdout.write(self.style.ERROR(error_message))
                    logger.error(error_message)
                    return

            try:
                with connection.cursor() as cursor:
                    # Ensure the table exists
                    cursor.execute("""
                    CREATE TABLE IF NOT EXISTS Reservation_Table (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_name TEXT,
                        status TEXT,
                        bp_eur REAL,
                        bp_eur_cz REAL,
                        delivery_month TEXT,
                        available INTEGER,
                        available_cz INTEGER,
                        released_rtd INTEGER,
                        brand TEXT,
                        panel_colour TEXT,
                        panel_design TEXT,
                        panel_power REAL,
                        inverter_power REAL,
                        nomenclature_group TEXT,
                        delivery_cw INTEGER,
                        length REAL,
                        height REAL,
                        width REAL,
                        pcs_ctn INTEGER,
                        pcs_pal INTEGER
                    )
                    """)

                    # Insert data from DataFrame into the table
                    for index, row in df.iterrows():
                        cursor.execute("""
                        INSERT INTO Reservation_Table (
                            product_name, status, bp_eur, bp_eur_cz, delivery_month, available,
                            available_cz, released_rtd, brand, panel_colour, panel_design,
                            panel_power, inverter_power, nomenclature_group, delivery_cw, length,
                            height, width, pcs_ctn, pcs_pal
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, [
                            row['product_name'], row['status'], row['bp_eur'], row['bp_eur_cz'], row['delivery_month'],
                            row['available'], row['available_cz'], row['released_rtd'], row['brand'], row['panel_colour'],
                            row['panel_design'], row['panel_power'], row['inverter_power'], row['nomenclature_group'],
                            row['delivery_cw'], row['length'], row['height'], row['width'], row['pcs_ctn'], row['pcs_pal']
                        ])
            except Exception as e:
                error_message = f"Database error: {e}"
                self.stdout.write(self.style.ERROR(error_message))
                logger.error(error_message)
                raise

            self.stdout.write(self.style.SUCCESS('Reservation_Table updated successfully'))
            logger.info('Reservation_Table updated successfully')

            # Optionally delete the temporary file
            os.remove(file_path)
        except Exception as e:
            error_message = f"Unhandled error: {e}"
            self.stdout.write(self.style.ERROR(error_message))
            logger.error(error_message)
            raise
