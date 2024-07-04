import pandas as pd
import json
import tempfile
import subprocess
import os

# Sample DataFrame data
data = {
    'product_name': ['Product 1', 'Product 2'],
    'status': ['Available', 'Available'],
    'bp_eur': [100, 150],
    'bp_eur_cz': [110, 160],
    'delivery_month': ['July', 'August'],
    'available': [10, 20],
    'available_cz': [5, 15],
    'released_rtd': [2, 3],
    'brand': ['Brand A', 'Brand B'],
    'panel_colour': ['Color A', 'Color B'],
    'panel_design': ['Design A', 'Design B'],
    'panel_power': [300, 350],
    'inverter_power': [500, 600],
    'nomenclature_group': ['Group 1', 'Group 2'],
    'delivery_cw': [30, 31],
    'length': [1.5, 1.6],
    'height': [1.1, 1.2],
    'width': [0.9, 0.95],
    'pcs_ctn': [1, 1],
    'pcs_pal': [10, 12]
}

# Convert to DataFrame
df = pd.DataFrame(data)

# Convert DataFrame to JSON
json_data = df.to_json(orient='records')

# Write JSON data to a temporary file
with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.json') as tmp_file:
    tmp_file.write(json_data)
    tmp_file_path = tmp_file.name

print(f"Temporary JSON file created at: {tmp_file_path}")

# Run the management command
try:
    result = subprocess.check_output(['python', 'manage.py', 'update_reservation_table', tmp_file_path], stderr=subprocess.STDOUT)
    print(result.decode('utf-8'))
except subprocess.CalledProcessError as e:
    print(e.output.decode('utf-8'))

# Clean up temporary file if it still exists
if os.path.exists(tmp_file_path):
    os.remove(tmp_file_path)
