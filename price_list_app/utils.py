import pandas as pd
from fpdf import FPDF
import os
from .models import NomenclatureMapping, PanelMapping

def generate_pdf(df, coefficients, warehouse, num_prices):
    # Similar to your script, implement the PDF generation logic here
    pdf_output = 'generated_files/price_list_with_selling_prices.pdf'
    # Implement your PDF generation logic
    return pdf_output

def generate_excel(df):
    excel_output = 'generated_files/price_list_with_selling_prices.xlsx'
    df.to_excel(excel_output, index=False)
    return excel_output

def get_nomenclature_mapping():
    return {mapping.key: mapping.value for mapping in NomenclatureMapping.objects.all()}

def get_panel_mapping():
    return {mapping.key: mapping.value for mapping in PanelMapping.objects.all()}

def read_csv():
    df = pd.read_csv(csv_file_path)
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df[numeric_columns] = df[numeric_columns].fillna(0)
    nomenclature_mapping = get_nomenclature_mapping()
    panel_mapping = get_panel_mapping()
    df['Group'] = df['nomenclature_group'].apply(lambda x: nomenclature_mapping.get(x[:3], 'Unknown'))
    df['panel_colour'] = df['panel_colour'].map(panel_mapping)
    df['panel_design'] = df['panel_design'].map(panel_mapping)
    return df