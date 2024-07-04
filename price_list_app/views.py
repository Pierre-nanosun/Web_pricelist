import os
import json
import pandas as pd
import logging
from PIL import Image
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, login
from django.contrib.auth.forms import AuthenticationForm
from django.conf import settings
from .forms import SelectionForm, CoefficientForm
from .models import Configuration, NomenclatureMapping, PanelMapping, Logo, PriceLabel
from fpdf import FPDF
from PyPDF2 import PdfReader, PdfWriter
from django.http import FileResponse, HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

# Constants
BASE_DIR = settings.BASE_DIR
csv_file_path = os.path.join(BASE_DIR, 'data', 'data.csv')
logos_dir = os.path.join(BASE_DIR, 'logos')
font_dir = os.path.join(BASE_DIR, 'price_list_app', 'static', 'fonts')
output_dir = os.path.join(BASE_DIR, 'static', 'generated_files')

# Ensure the output directory exists
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

numeric_columns = [
    'available', 'available_cz', 'bp_eur', 'bp_eur_cz',
    'panel_power', 'length', 'width', 'height', 'pcs_pal', 'pcs_ctn'
]

def get_pricelabel_headers():
    headers = {}
    other_headers = {}
    for item in PriceLabel.objects.all():
        if item.product_group == 'Other':
            other_headers = {
                'price_label_1': item.price_label_1,
                'price_label_2': item.price_label_2,
                'price_label_3': item.price_label_3,
                'price_label_4': item.price_label_4,
            }
        headers[item.product_group] = {
            'price_label_1': item.price_label_1,
            'price_label_2': item.price_label_2,
            'price_label_3': item.price_label_3,
            'price_label_4': item.price_label_4,
        }
    # Add fallback for groups not having specific headers
    for group in headers:
        for i in range(1, 5):
            headers[group].setdefault(f'price_label_{i}', other_headers.get(f'price_label_{i}', f'price_label_{i}'))
    headers['Other'] = other_headers  # Ensure 'Other' group is always included
    return headers


def get_mappings():
    nomenclature_mapping = {
        item.key: item.value for item in NomenclatureMapping.objects.all()
    }
    panel_mapping = {
        item.key: item.value for item in PanelMapping.objects.all()
    }
    return nomenclature_mapping, panel_mapping

def read_csv():
    df = pd.read_csv(csv_file_path)
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df[numeric_columns] = df[numeric_columns].fillna(0)
    nomenclature_mapping, panel_mapping = get_mappings()
    df['Group'] = df['nomenclature_group'].apply(lambda x: nomenclature_mapping.get(x[:3], 'Unknown'))
    df['panel_colour'] = df['panel_colour'].map(panel_mapping)
    df['panel_design'] = df['panel_design'].map(panel_mapping)
    return df

def home(request):
    return render(request, 'price_list_app/home.html')

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')

@login_required
def select_products(request):
    if request.method == 'POST':
        form = SelectionForm(request.POST)
        if form.is_valid():
            selected_groups = list(form.cleaned_data['groups'].values_list('value', flat=True))
            selected_brands = list(form.cleaned_data['brands'].values_list('name', flat=True))
            warehouse = form.cleaned_data['warehouse']
            num_prices = form.cleaned_data['num_prices']
            config, created = Configuration.objects.get_or_create(
                user=request.user,
                selected_groups=json.dumps(selected_groups),
                selected_brands=json.dumps(selected_brands),
                warehouse=warehouse,
                num_prices=num_prices,
                defaults={'coefficients': json.dumps({})}
            )
            return redirect('input_coefficients', config_id=config.id)
    else:
        form = SelectionForm()
    return render(request, 'price_list_app/select_products.html', {'form': form})

@login_required
def input_coefficients(request, config_id):
    config = get_object_or_404(Configuration, id=config_id)
    selected_groups = json.loads(config.selected_groups)
    num_prices = config.num_prices

    try:
        default_config = json.loads(config.coefficients) if config.coefficients else {}
    except json.JSONDecodeError:
        default_config = {}

    # Fetch default headers from PriceLabel
    pricelabel_headers = get_pricelabel_headers()

    if request.method == 'POST':
        form = CoefficientForm(request.POST, groups=selected_groups, num_prices=num_prices,
                               default_config=default_config, pricelabel_headers=pricelabel_headers, warehouse=config.warehouse)
        if form.is_valid():
            coefficients = {}
            for group in selected_groups:
                coefficients[group] = {}
                for i in range(1, num_prices + 1):
                    coefficients[group][f'operation_{i}'] = form.cleaned_data[f'{group}_operation_{i}']
                    coefficients[group][f'coefficient_{i}'] = form.cleaned_data[f'{group}_coefficient_{i}']
                    coefficients[group][f'header_{i}'] = form.cleaned_data[f'{group}_header_{i}']
            config.coefficients = json.dumps(coefficients)
            config.save()
            return redirect('generate_files', config_id=config.id)
    else:
        form = CoefficientForm(groups=selected_groups, num_prices=num_prices, default_config=default_config,
                               pricelabel_headers=pricelabel_headers, warehouse=config.warehouse)

    dynamic_fields = [
        {
            "group": group,
            "fields": [
                {
                    "operation": f"{group}_operation_{i}",
                    "coefficient": f"{group}_coefficient_{i}",
                    "header": f"{group}_header_{i}",
                    "default_header": default_config.get(group, {}).get(f'header_{i}', pricelabel_headers.get(group, {}).get(f'price_label_{i}', pricelabel_headers.get('Other', {}).get(f'price_label_{i}', f'price_label_{i}')))
                } for i in range(1, num_prices + 1)
            ]
        } for group in selected_groups
    ]

    return render(request, 'price_list_app/input_coefficients.html',
                  {'form': form, 'num_prices_range': range(1, num_prices + 1), 'dynamic_fields': dynamic_fields})


def load_logos():
    logo_dict = {}
    logos = Logo.objects.all()
    for logo in logos:
        logo_dict[os.path.splitext(logo.name)[0]] = logo.file.path
    return logo_dict

def convert_to_non_interlaced(image_path):
    try:
        with Image.open(image_path) as img:
            if img.info.get('interlace'):
                non_interlaced_path = image_path.replace('.png', '_non_interlaced.png')
                img.save(non_interlaced_path, interlace=False)
                return non_interlaced_path
    except Exception as e:
        logger.error(f"Error converting image: {e}")
    return image_path

@login_required
def generate_files(request, config_id):
    config = get_object_or_404(Configuration, id=config_id)
    selected_groups = json.loads(config.selected_groups)
    selected_brands = json.loads(config.selected_brands)
    warehouse = config.warehouse
    num_prices = config.num_prices
    coefficients = json.loads(config.coefficients)

    df = read_csv()
    df = df[df['Group'].isin(selected_groups)]
    df = df[df['brand'].isin(selected_brands)]

    def calculate_selling_price(bp_price, operation, coefficient):
        if operation == "*":
            return bp_price * coefficient
        elif operation == "+":
            return bp_price + coefficient
        return bp_price

    def apply_coefficients(row):
        group = row['Group']
        bp_price = row['bp_eur_cz'] if warehouse == 'Decin' else row['bp_eur']
        for j in range(1, num_prices + 1):
            op = coefficients.get(group, {}).get(f'operation_{j}', '*')
            coeff = coefficients.get(group, {}).get(f'coefficient_{j}', 1.2)
            price = calculate_selling_price(bp_price, op, coeff)
            row[f'price_label_{j}'] = round(price, 3) if group == 'Panels' else round(price, 0)
        return row

    df = df.apply(apply_coefficients, axis=1)

    for j in range(1, num_prices + 1):
        price_col = f'price_label_{j}'
        if price_col not in df.columns:
            df[price_col] = 0

    availability_column = 'available_cz' if warehouse == 'Decin' else 'available'
    df = df[df[availability_column] > 0]

    grouped_df = df.groupby(['Group', 'brand', 'product_name'], as_index=False).agg({
        'available': 'sum',
        'available_cz': 'sum',
        'bp_eur': 'max',
        'bp_eur_cz': 'max',
        **{f'price_label_{j}': 'max' for j in range(1, num_prices + 1)},
        'delivery_month': 'first',
        'delivery_cw': 'first',
        'panel_power': 'first',
        'panel_colour': 'first',
        'panel_design': 'first',
        'length': 'first',
        'width': 'first',
        'height': 'first',
        'pcs_pal': 'first',
        'pcs_ctn': 'first'
    })

    grouped_df = grouped_df[grouped_df[availability_column] > 0]
    custom_order = list(get_mappings()[0].values())
    grouped_df['Group'] = pd.Categorical(grouped_df['Group'], categories=custom_order, ordered=True)
    grouped_df = grouped_df.sort_values('Group').reset_index(drop=True)

    # Get headers from coefficients
    headers = {}
    for group in selected_groups:
        headers[group] = {}
        for i in range(1, num_prices + 1):
            headers[group][f'price_label_{i}'] = coefficients.get(group, {}).get(f'header_{i}', f'price_label_{i}')
    # Ensure 'Other' group is always included
    if 'Other' not in headers:
        headers['Other'] = get_pricelabel_headers().get('Other', {})

    final_columns = [
        'Group', 'brand', 'product_name', 'available', 'delivery_month', 'delivery_cw',
        'panel_power', 'panel_colour', 'panel_design', 'length', 'width', 'height', 'pcs_pal', 'pcs_ctn',
        *[f'price_label_{j}' for j in range(1, num_prices + 1)]
    ]
    final_df = grouped_df[final_columns]
    final_df = final_df.astype(str)
    empty_values = ['0', 'NaN', 'None', 'NULL', 'nan', '0.0']
    final_df.replace(empty_values, "", inplace=True)

    nomenclature_mapping, panel_mapping = get_mappings()

    column_rename_dict = {
        'Group': 'Product Group',
        'brand': 'Brand',
        'product_name': 'Product Name',
        'available': 'Available',
        'delivery_month': 'Delivery',
        'delivery_cw': 'CW',
        'panel_power': 'Power(W)',
        'panel_colour': 'Colour',
        'panel_design': 'Design',
        'length': 'Length',
        'width': 'Width',
        'height': 'Height',
        'pcs_pal': 'Pcs Pal',
        'pcs_ctn': 'Pcs ctn',
    }

    final_df.rename(columns=column_rename_dict, inplace=True)

    def format_numbers(value):
        try:
            if float(value).is_integer():
                return "{:,.0f}".format(float(value)).replace(",", " ")
            else:
                return "{:,.3f}".format(float(value)).replace(",", " ")
        except ValueError:
            return str(value)

    final_df = final_df.applymap(format_numbers)

    logo_dict = load_logos()

    class PDF(FPDF):
        def __init__(self, orientation='P'):
            super().__init__(orientation)
            self.orientation = orientation
            self.toc = []

        def header(self):
            self.set_font('DejaVu', 'B', 10)
            self.cell(0, 10, 'Price List', 0, 1, 'C')

        def footer(self):
            self.set_y(-15)
            self.set_font('DejaVu', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

        def chapter_title(self, title, group=False):
            if self.get_y() > self.h - 70:
                self.add_page()
            self.set_font('DejaVu', 'B', 10)
            self.cell(0, 10, title, 0, 1, 'L')
            self.ln(2)
            link = self.add_link()
            self.set_link(link, page=self.page_no())
            if group:
                self.toc.append((title, self.page_no(), link))
            else:
                self.toc.append((f"{self.current_group}: {title}", self.page_no(), link))

        def chapter_body(self, body):
            self.set_font('DejaVu', '', 8)
            self.multi_cell(0, 10, body)
            self.ln()

        def add_banner(self, logo_filename, height=20):
            if logo_filename in logo_dict:
                logo_path = logo_dict[logo_filename]
                if os.path.isfile(logo_path):
                    logo_path = convert_to_non_interlaced(logo_path)
                    self.image(logo_path, x=12, y=self.get_y(), h=height)
            else:
                logo_path = logo_dict["NANOSUN"]
                if os.path.isfile(logo_path):
                    logo_path = convert_to_non_interlaced(logo_path)
                    self.image(logo_path, x=12, y=self.get_y(), h=height)
            self.ln(height)

        def add_table(self, dataframe, group, headers):
            # Drop unnecessary columns and empty columns
            dataframe = dataframe.drop(columns=['Product Group', 'Brand'], errors='ignore')
            dataframe = dataframe.loc[:, ~(dataframe == "").all()]

            # Create a copy of the dataframe to avoid modifying the original one
            dataframe_copy = dataframe.copy()

            # Replace column names based on the provided headers for the specific group
            for col in dataframe.columns:
                if col in headers[group]:
                    dataframe_copy.rename(columns={col: headers[group][col]}, inplace=True)

            self.set_font('DejaVu', 'B', 7)
            headers_list = dataframe_copy.columns.tolist()
            page_width = self.w - 2 * self.l_margin
            cell_widths = {header: self.get_string_width(header) + 2 for header in headers_list}

            for header in headers_list:
                for value in dataframe_copy[header]:
                    cell_widths[header] = max(cell_widths[header], self.get_string_width(str(value)) + 2)
            cell_widths['Product Name'] = max(cell_widths['Product Name'], 50)
            total_width = sum(cell_widths.values())
            scale = page_width / total_width
            for header in cell_widths:
                cell_widths[header] *= scale

            for header in headers_list:
                self.cell(cell_widths[header], 10, header.replace('_', ' ').title(), 1, 0, 'C')
            self.ln()

            self.set_font('DejaVu', '', 7)
            for row in dataframe_copy.itertuples(index=False):
                for header in headers_list:
                    self.cell(cell_widths[header], 10, str(row[headers_list.index(header)]), 1, 0)
                self.ln()

        def add_toc_page(self):
            max_pages = 2
            initial_font_size = 10
            data = self._prepare_data()
            row_height = 6

            while True:
                self.set_auto_page_break(auto=True, margin=15)
                self.add_page()
                self._render_toc(data, initial_font_size, row_height)
                pages_used = self.page_no()

                if pages_used <= max_pages:
                    break

                initial_font_size -= 0.5
                row_height -= 0.2
                self._reset_document()

            self.output(os.path.join(output_dir, 'table_of_contents.pdf'))

        def _prepare_data(self):
            data = []
            temp_title = ""
            for title, page, link in self.toc:
                if ": " in title:
                    group, brand = title.split(": ", 1)
                    data.append([temp_title, brand, page])
                    temp_title = ""
                else:
                    temp_title = title
            return data

        def _render_toc(self, data, font_size, row_height):
            self.set_font('DejaVu', 'B', font_size)
            self.cell(0, 8, 'Table of Contents', 0, 1, 'C')
            self.ln(1)
            self.set_font('DejaVu', '', font_size - 2)

            col_width = (self.w - 2 * self.l_margin) / 3
            for i, row in enumerate(data):
                self.set_text_color(0, 0, 0)
                self.set_font('DejaVu', 'B', font_size - 2)

                # Draw chapter cell
                self.cell(col_width, row_height, str(row[0]), 0, 0, 'L')
                x_chapter_end = self.get_x()

                # Draw brand cell
                self.cell(col_width, row_height, str(row[1]), 0, 0, 'L')
                x_brand_end = self.get_x()

                # Draw page cell
                self.cell(col_width, row_height, str(row[2]), 0, 0, 'R')
                x_page_end = self.get_x()

                # Draw dashed lines
                y = self.get_y() + row_height
                self._draw_dashed_line(x_chapter_end, y, x_brand_end - x_chapter_end, row_height)
                self._draw_dashed_line(x_brand_end, y, x_page_end - x_brand_end, row_height)

                self.ln(row_height)
            self.ln(2)

        def _draw_dashed_line(self, x, y, width, height, dash_length=2):
            self.set_draw_color(0, 0, 0)
            self.set_line_width(0.2)
            x_start = x
            x_end = x + width
            while x_start < x_end:
                self.line(x_start, y, x_start + dash_length, y)
                x_start += dash_length * 2

        def _reset_document(self):
            self.pages = []
            self.page_no_ = 0
            self.num_pages = 0
            self._outlines = []
            self._current_page = None
            self.add_page()

    pdf = PDF(orientation='L')
    pdf.add_font('DejaVu', '', os.path.join(font_dir, 'DejaVuSans.ttf'), uni=True)
    pdf.add_font('DejaVu', 'B', os.path.join(font_dir, 'DejaVuSans-Bold.ttf'), uni=True)
    pdf.add_font('DejaVu', 'I', os.path.join(font_dir, 'DejaVuSans-Oblique.ttf'), uni=True)

    if 'Product Group' in final_df.columns:
        for group, group_df in final_df.groupby('Product Group', sort=False):
            pdf.add_page()
            pdf.current_group = group
            pdf.chapter_title(f"{group} Products", group=True)
            for brand, brand_df in group_df.groupby('Brand'):
                pdf.chapter_title(brand)
                pdf.add_banner(brand)
                pdf.ln(5)
                pdf.add_table(brand_df, group, headers)
                pdf.ln(10)

    content_pdf_output = os.path.join(output_dir, 'content.pdf')
    pdf.output(content_pdf_output)

    toc_temp = PDF(orientation='L')
    toc_temp.add_font('DejaVu', '', os.path.join(font_dir, 'DejaVuSans.ttf'), uni=True)
    toc_temp.add_font('DejaVu', 'B', os.path.join(font_dir, 'DejaVuSans-Bold.ttf'), uni=True)
    toc_temp.add_font('DejaVu', 'I', os.path.join(font_dir, 'DejaVuSans-Oblique.ttf'), uni=True)
    toc_temp.toc = pdf.toc
    toc_temp.add_toc_page()

    toc_temp_output = os.path.join(output_dir, 'toc_temp.pdf')
    toc_temp.output(toc_temp_output)

    toc_temp_reader = PdfReader(toc_temp_output)
    toc_pages_count = len(toc_temp_reader.pages)

    adjusted_toc = [(title, page + toc_pages_count, link) for title, page, link in pdf.toc]

    final_toc = PDF(orientation='L')
    final_toc.add_font('DejaVu', '', os.path.join(font_dir, 'DejaVuSans.ttf'), uni=True)
    final_toc.add_font('DejaVu', 'B', os.path.join(font_dir, 'DejaVuSans-Bold.ttf'), uni=True)
    final_toc.add_font('DejaVu', 'I', os.path.join(font_dir, 'DejaVuSans-Oblique.ttf'), uni=True)
    final_toc.toc = adjusted_toc
    final_toc.add_toc_page()

    final_toc_output = os.path.join(output_dir, 'final_toc.pdf')
    final_toc.output(final_toc_output)

    final_toc_reader = PdfReader(final_toc_output)
    content_pdf_reader = PdfReader(content_pdf_output)
    final_pdf_writer = PdfWriter()

    for page_num in range(len(final_toc_reader.pages)):
        final_pdf_writer.add_page(final_toc_reader.pages[page_num])

    for page_num in range(len(content_pdf_reader.pages)):
        final_pdf_writer.add_page(content_pdf_reader.pages[page_num])

    final_output = os.path.join(output_dir, 'price_list_with_selling_prices.pdf')
    with open(final_output, 'wb') as f:
        final_pdf_writer.write(f)

    os.remove(content_pdf_output)
    os.remove(toc_temp_output)
    os.remove(final_toc_output)

    excel_output = os.path.join(output_dir, 'price_list_with_selling_prices.xlsx')
    final_df.to_excel(excel_output, index=False)

    return redirect('results')



@login_required
def download_pdf(request):
    file_path = os.path.join(output_dir, 'price_list_with_selling_prices.pdf')
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), content_type='application/pdf', as_attachment=True, filename='price_list_with_selling_prices.pdf')
    return redirect('results')

@login_required
def download_excel(request):
    file_path = os.path.join(output_dir, 'price_list_with_selling_prices.xlsx')
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, filename='price_list_with_selling_prices.xlsx')
    return redirect('results')

@login_required
def view_pdf(request):
    file_path = os.path.join(output_dir, 'price_list_with_selling_prices.pdf')
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), content_type='application/pdf')
    else:
        return HttpResponse("File not found", status=404)

@csrf_exempt
def update_csv_view(request):
    secure_token = 'iRQScq0YJtJxz8HQXYCORsh86OXQJcxt4BEmGXM5CTbM95ys6A'  # Replace with your secure token
    if request.method == 'POST':
        received_token = request.POST.get('token')

        if received_token == secure_token:
            data = request.POST.get('data')
            if not data:
                logger.error("No data provided")
                return HttpResponse("No data provided", status=400)

            try:
                df = pd.read_json(data)
                csv_file_path = os.path.join(settings.BASE_DIR, 'data', 'data.csv')
                df.to_csv(csv_file_path, index=False)
                return HttpResponse('data.csv updated successfully')
            except Exception as e:
                logger.error(f"An error occurred: {e}")
                return HttpResponse(f"An error occurred: {e}", status=500)
        else:
            return HttpResponseForbidden('Forbidden')
    else:
        logger.error("Forbidden access attempt")
        return HttpResponseForbidden('Forbidden')

@login_required
def results(request):
    return render(request, 'price_list_app/results.html')
