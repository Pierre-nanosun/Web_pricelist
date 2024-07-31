from fpdf import FPDF
import os
import json
import pandas as pd
from PIL import Image
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, login
from django.contrib.auth.forms import AuthenticationForm
from django.conf import settings
from .forms import SelectionForm, CoefficientForm
from .models import Configuration, NomenclatureMapping, PanelMapping, Logo, PriceLabel, Brand, Promotion, BackgroundImage
from PyPDF2 import PdfReader, PdfWriter
from django.http import FileResponse, HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
from django.contrib import messages
import logging
from unidecode import unidecode
from django.template.loader import render_to_string
import csv

def robots_txt(request):
    content = render_to_string('price_list_app/robots.txt')
    return HttpResponse(content, content_type='text/plain')

logger = logging.getLogger(__name__)

# Constants
BASE_DIR = settings.BASE_DIR
csv_file_path = os.path.join(BASE_DIR, 'data', 'data.csv')
csv_datasheet_file_path = os.path.join(BASE_DIR, 'data', 'datasheet.csv')
logos_dir = os.path.join(BASE_DIR, 'logos')
font_dir = os.path.join(BASE_DIR, 'price_list_app', 'static', 'fonts')
output_dir = os.path.join(BASE_DIR, 'static', 'generated_files')


df_links = pd.read_csv(csv_datasheet_file_path)
product_links = dict(zip(df_links['Product Name'], df_links['link']))

# Ensure the output directory exists
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

numeric_columns = [
    'available', 'available_cz', 'bp_eur', 'bp_eur_cz',
    'panel_power', 'length', 'width', 'height', 'pcs_pal', 'pcs_ctn'
]


def import_promotions_from_csv(file_data):
    reader = csv.DictReader(file_data)
    for row in reader:
        product_name = row.get('product_name')
        selling_price = row.get('selling_price')
        if product_name and selling_price:
            Promotion.objects.update_or_create(
                product_name=product_name,
                defaults={'selling_price': selling_price}
            )

def upload_csv_view(request):
    if request.method == 'POST':
        csv_file = request.FILES['csv_file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'File is not CSV type')
            return redirect('admin:app_list', app_label='price_list_app')

        try:
            # Open the file in text mode by passing it directly to csv.reader or csv.DictReader
            csv_file_data = csv_file.read().decode('utf-8').splitlines()
            import_promotions_from_csv(csv_file_data)
            messages.success(request, 'Promotions imported successfully.')
        except Exception as e:
            messages.error(request, f"An error occurred: {e}")

        return redirect('admin:app_list', app_label='price_list_app')

    return redirect('admin:app_list', app_label='price_list_app')

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
    nomenclature_mapping, _ = get_mappings()
    df['Group'] = df['nomenclature_group'].apply(lambda x: nomenclature_mapping.get(x[:3], 'Unknown'))
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
    return redirect('logout')

@login_required
def select_products(request):
    if request.method == 'POST':
        if 'delete_config' in request.POST:
            config_id = request.POST.get('configurations')
            if config_id:
                Configuration.objects.filter(id=config_id, user=request.user).delete()
                return redirect('select_products')
        elif 'modify_config' in request.POST:
            config_id = request.POST.get('configurations')
            if config_id:
                return redirect('input_coefficients', config_id=config_id)
        elif 'generate_config' in request.POST:
            config_id = request.POST.get('configurations')
            if config_id:
                return redirect('generate_files', config_id=config_id)
        else:
            form = SelectionForm(request.POST, user=request.user)
            if form.is_valid():
                selected_groups = list(form.cleaned_data['groups'].values_list('value', flat=True))
                warehouse = form.cleaned_data['warehouse']
                num_prices = form.cleaned_data['num_prices']
                selected_columns = form.cleaned_data['selected_columns']
                select_all_brands = form.cleaned_data.get('select_all_brands', False)

                if select_all_brands:
                    selected_brands = []  # Store an empty list as we will handle this dynamically
                else:
                    selected_brands = list(form.cleaned_data['brands'].values_list('name', flat=True))

                filters = {
                    'delivery_month_start': form.cleaned_data['delivery_month_start'].strftime('%Y-%m') if form.cleaned_data['delivery_month_start'] else None,
                    'delivery_month_end': form.cleaned_data['delivery_month_end'].strftime('%Y-%m') if form.cleaned_data['delivery_month_end'] else None,
                    'panel_power_min': form.cleaned_data['panel_power_min'],
                    'panel_power_max': form.cleaned_data['panel_power_max'],
                    'panel_colour': list(form.cleaned_data['panel_colour'].values_list('name', flat=True)) if form.cleaned_data['panel_colour'] else [],
                    'panel_design': list(form.cleaned_data['panel_design'].values_list('name', flat=True)) if form.cleaned_data['panel_design'] else [],
                    'length_min': form.cleaned_data['length_min'],
                    'length_max': form.cleaned_data['length_max'],
                    'height_min': form.cleaned_data['height_min'],
                    'height_max': form.cleaned_data['height_max'],
                    'width_min': form.cleaned_data['width_min'],
                    'width_max': form.cleaned_data['width_max'],
                    'available': form.cleaned_data['available'],
                    'power_available': form.cleaned_data['power_available'],
                    'pal_available' : form.cleaned_data['pal_available'],
                    'ctn_available' : form.cleaned_data['ctn_available'],
                    'length_height_limit': form.cleaned_data['length_height_limit'],
                    'urgent_stocks' : form.cleaned_data['urgent_stocks'],
                    'no_delivery_date': form.cleaned_data['no_delivery_date'],
                    'NoBackground': form.cleaned_data['NoBackground'],
                    'NoTOC': form.cleaned_data['NoTOC'],

                }

                config_name = f"Configuration {datetime.now().strftime('%Y%m%d%H%M%S')}"
                config = Configuration.objects.create(
                    user=request.user,
                    name=config_name,
                    selected_groups=json.dumps(selected_groups),
                    selected_brands=json.dumps(selected_brands),
                    warehouse=warehouse,
                    num_prices=num_prices,
                    coefficients=json.dumps({}),
                    select_all_brands=select_all_brands,
                    filters=json.dumps(filters),
                    selected_columns=json.dumps(selected_columns)
                )
                return redirect('input_coefficients', config_id=config.id)
            else:
                messages.error(request, 'Form is invalid. Please correct the errors and try again. [Product type]')
    else:
        form = SelectionForm(user=request.user)
    return render(request, 'price_list_app/select_products.html', {'form': form})

@login_required
def input_coefficients(request, config_id):
    config = get_object_or_404(Configuration, id=config_id)
    selected_groups = json.loads(config.selected_groups)
    num_prices = config.num_prices
    pricelabel_headers = get_pricelabel_headers()
    default_config = {}

    try:
        other_defaults = PriceLabel.objects.get(product_group='Other')
    except PriceLabel.DoesNotExist:
        other_defaults = None

    for group in selected_groups:
        try:
            price_label = PriceLabel.objects.get(product_group=group)
        except PriceLabel.DoesNotExist:
            price_label = other_defaults

        if price_label:
            default_config[group] = {
                'operation_1': price_label.operation_1,
                'coefficient_1': price_label.coefficient_1,
                'header_1': price_label.price_label_1,
                'operation_2': price_label.operation_2,
                'coefficient_2': price_label.coefficient_2,
                'header_2': price_label.price_label_2,
                'operation_3': price_label.operation_3,
                'coefficient_3': price_label.coefficient_3,
                'header_3': price_label.price_label_3,
                'operation_4': price_label.operation_4,
                'coefficient_4': price_label.coefficient_4,
                'header_4': price_label.price_label_4,
            }
        else:
            default_config[group] = {
                'operation_1': '*',
                'coefficient_1': 1.0,
                'header_1': pricelabel_headers.get(group, {}).get('price_label_1', 'Price Label 1'),
                'operation_2': '*',
                'coefficient_2': 1.0,
                'header_2': pricelabel_headers.get(group, {}).get('price_label_2', 'Price Label 2'),
                'operation_3': '*',
                'coefficient_3': 1.0,
                'header_3': pricelabel_headers.get(group, {}).get('price_label_3', 'Price Label 3'),
                'operation_4': '*',
                'coefficient_4': 1.0,
                'header_4': pricelabel_headers.get(group, {}).get('price_label_4', 'Price Label 4'),
            }

    if request.method == 'POST':
        form = CoefficientForm(request.POST, groups=selected_groups, num_prices=num_prices,
                               default_config=default_config, pricelabel_headers=pricelabel_headers, warehouse=config.warehouse)
        if form.is_valid():
            config.name = form.cleaned_data['name']
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
        form = CoefficientForm(initial={'name': config.name}, groups=selected_groups, num_prices=num_prices, default_config=default_config,
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
    user_directory = os.path.join(output_dir, request.user.username)
    if not os.path.exists(user_directory):
        os.makedirs(user_directory)

    selected_groups = json.loads(config.selected_groups)
    warehouse = config.warehouse
    num_prices = config.num_prices
    coefficients = json.loads(config.coefficients)
    filters = json.loads(config.filters)

    # Handle dynamic selection of brands
    if config.select_all_brands:
        selected_brands = list(Brand.objects.all().values_list('name', flat=True))
    else:
        selected_brands = json.loads(config.selected_brands)

    df = read_csv()
    df = df[df['Group'].isin(selected_groups)]
    df = df[df['brand'].isin(selected_brands)]


    # Apply filters
    if filters.get('no_delivery_date'):
        df = df[df['delivery_month'].isnull()]
    else:
        df['delivery_month'] = pd.to_datetime(df['delivery_month']).dt.strftime('%Y-%m')
        if filters.get('delivery_month_start'):
            df = df[df['delivery_month'] >= filters['delivery_month_start']]
        if filters.get('delivery_month_end'):
            df = df[df['delivery_month'] <= filters['delivery_month_end']]
    if filters.get('panel_power_min') is not None:
        df = df[df['panel_power'] >= filters['panel_power_min']]
    if filters.get('panel_power_max') is not None:
        df = df[df['panel_power'] <= filters['panel_power_max']]
    if filters.get('panel_colour'):
        df = df[df['panel_colour'].isin(filters['panel_colour'])]
    if filters.get('panel_design'):
        df = df[df['panel_design'].isin(filters['panel_design'])]
    if filters.get('length_min') is not None:
        df = df[df['length'] >= filters['length_min']]
    if filters.get('length_max') is not None:
        df = df[df['length'] <= filters['length_max']]
    if filters.get('height_min') is not None:
        df = df[df['height'] >= filters['height_min']]
    if filters.get('height_max') is not None:
        df = df[df['height'] <= filters['height_max']]
    if filters.get('width_min') is not None:
        df = df[df['width'] >= filters['width_min']]
    if filters.get('width_max') is not None:
        df = df[df['width'] <= filters['width_max']]
    if filters.get('available') is not None:
        df = df[df['available'] >= filters['available']]
    if filters.get('power_available') is not None:
        df['power_available'] = (df['available'] * df['panel_power']) / 1000
        df = df[df['power_available'] >= filters['power_available']]

    if filters.get('pal_available') is not None:
        df = df[df['available']/df['pcs_pal']  >= filters['pal_available']]

    if filters.get('ctn_available') is not None:
        df = df[df['pcs_ctn'] >= 1]
        df = df[df['available']/df['pcs_ctn'] >= filters['ctn_available']]

    if filters.get('length_height_limit'):
        def product_of_two_largest(row):
            largest_two = sorted([row['length'], row['height'], row['width']], reverse=True)[:2]
            return largest_two[0]/1000 * largest_two[1]/1000

        df['product_of_two_largest'] = df.apply(product_of_two_largest, axis=1)
        df = df[df['product_of_two_largest'] <= 2]
        df = df.drop(columns=['product_of_two_largest'])

    if filters.get('urgent_stocks'):
        # Convert 'min_receipt_date' to a datetime format
        df['min_receipt_date'] = pd.to_datetime(df['min_receipt_date'], unit='ms')

        # Calculate the date two months ago from today
        two_months_ago = datetime.today() - timedelta(days=60)

        # Filter the DataFrame where the difference is greater than two months
        df = df[df['min_receipt_date'] < two_months_ago]


    _, panel_mapping = get_mappings()
    df['panel_colour'] = df['panel_colour'].map(panel_mapping)
    df['panel_design'] = df['panel_design'].map(panel_mapping)

    def calculate_selling_price(bp_price, operation, coefficient):
        if operation == "*":
            return bp_price * coefficient
        elif operation == "+":
            return bp_price + coefficient
    def apply_coefficients(row):
        group = row['Group']
        bp_price = row['bp_eur_cz'] if warehouse == 'Decin' else row['bp_eur']
        for j in range(1, num_prices + 1):
            op = coefficients.get(group, {}).get(f'operation_{j}', '*')
            coeff = coefficients.get(group, {}).get(f'coefficient_{j}', 1.2)
            price = calculate_selling_price(bp_price, op, coeff)
            if group == 'Panels':
                row[f'price_label_{j}'] = round(price, 4)
            else:
                row[f'price_label_{j}'] = round(price, 0)
        return row

    if warehouse == 'Decin':
        df['available'] = df['available_cz']
    else:
        df['available'] = df['available'] - df['available_cz']

    df = df[df['available'] > 0]
    df = df.apply(apply_coefficients, axis=1)

    for j in range(1, num_prices + 1):
        price_col = f'price_label_{j}'
        if price_col not in df.columns:
            df[price_col] = 0

    grouped_df = df.groupby(['Group', 'brand', 'product_name'], as_index=False).agg({
        'available': 'sum',
        'bp_eur': 'max',
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

    grouped_df = grouped_df[grouped_df['available'] > 0]
    custom_order = list(get_mappings()[0].values())
    grouped_df['Group'] = pd.Categorical(grouped_df['Group'], categories=custom_order, ordered=True)
    grouped_df = grouped_df.sort_values('Group').reset_index(drop=True)

    headers = {}
    for group in selected_groups:
        headers[group] = {}
        for i in range(1, num_prices + 1):
            headers[group][f'price_label_{i}'] = coefficients.get(group, {}).get(f'header_{i}', f'price_label_{i}')
    if 'Other' not in headers:
        headers['Other'] = get_pricelabel_headers().get('Other', {})

    selected_columns = json.loads(config.selected_columns)
    final_columns = ['Group', 'brand', 'product_name'] + selected_columns + [f'price_label_{j}' for j in range(1, num_prices + 1)]
    final_df = grouped_df[final_columns]
    final_df = final_df.astype(str)
    empty_values = ['0', 'NaN', 'None', 'NULL', 'nan', '0.0']
    final_df.replace(empty_values, "", inplace=True)

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
        def __init__(self, orientation='P', background_image=None):
            super().__init__(orientation)
            self.background_image = background_image
            self.toc = []

        def header(self):
            if self.background_image:
                self.image(self.background_image, x=0, y=0, w=self.w, h=self.h)
            self.set_font('DejaVu', 'B', 10)
            self.cell(0, 10, 'Price List', 0, 1, 'C')


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
            dataframe = dataframe.drop(columns=['Product Group', 'Brand'], errors='ignore')
            dataframe = dataframe.loc[:, ~(dataframe == "").all()]
            dataframe_copy = dataframe.copy()
            for col in dataframe.columns:
                if col in headers[group]:
                    dataframe_copy.rename(columns={col: headers[group][col]}, inplace=True)

            self.set_font('DejaVu', 'B', 7)
            headers_list = dataframe_copy.columns.tolist()
            page_width = self.w - 2 * self.l_margin
            cell_widths = {}
            for header in headers_list:
                max_content_width = max(self.get_string_width(str(value)) for value in dataframe_copy[header]) + 4
                header_width = self.get_string_width(header.replace('_', ' ').title()) + 4
                cell_widths[header] = max(max_content_width, header_width)
            if "Product Name" in cell_widths:
                cell_widths["Product Name"] += 0.5 * self.get_string_width(' ')
                cell_widths["Product Name"] += self.get_string_width(' ' * 3)
            total_width = sum(cell_widths.values())
            scale = page_width / total_width
            for header in cell_widths:
                cell_widths[header] *= scale

            def split_text(text, cell_width, max_lines=2):
                words = text.split(' ')
                lines = []
                current_line = words[0]
                for word in words[1:]:
                    if self.get_string_width(current_line + ' ' + word) <= cell_width - 4:
                        current_line += ' ' + word
                    else:
                        lines.append(current_line)
                        current_line = word
                    if len(lines) >= max_lines - 1:
                        break
                lines.append(current_line)
                if len(lines) > max_lines:
                    lines = lines[:max_lines]
                return lines

            max_lines = 2
            header_lines_dict = {}
            for header in headers_list:
                header_lines = split_text(header.replace('_', ' ').title(), cell_widths[header], max_lines=max_lines)
                header_lines_dict[header] = header_lines
                max_lines = max(max_lines, len(header_lines))

            line_height = 5
            header_height = max_lines * line_height
            for header in headers_list:
                if len(header_lines_dict[header]) > 1:
                    cell_widths[header] *= 0.8
            total_width = sum(cell_widths.values())
            scale = page_width / total_width
            for header in cell_widths:
                cell_widths[header] *= scale

            def draw_headers():
                y_start = self.get_y()
                for header in headers_list:
                    x_start = self.get_x()
                    for i, line in enumerate(header_lines_dict[header]):
                        self.set_xy(x_start, y_start + i * line_height)
                        self.cell(cell_widths[header], line_height, line, 0, 0, 'C')
                    self.set_xy(x_start + cell_widths[header], y_start)
                self.set_y(y_start + header_height)
                self.set_y(y_start)
                x_start = self.l_margin
                for header in headers_list:
                    self.set_xy(x_start, y_start)
                    self.multi_cell(cell_widths[header], header_height, '', 1, 'C')
                    x_start += cell_widths[header]

            draw_headers()

            self.set_font('DejaVu', '', 7)
            for row in dataframe_copy.itertuples(index=False):
                row_lines_dict = {}
                max_row_lines = 1
                for header in headers_list:
                    cell_text = str(row[headers_list.index(header)])
                    if header in ["Colour", "Product Name", "Design"]:
                        row_lines = split_text(cell_text, cell_widths[header], max_lines=2)
                    else:
                        row_lines = [cell_text]
                    row_lines_dict[header] = row_lines
                    max_row_lines = max(max_row_lines, len(row_lines))

                row_height = max_row_lines * line_height
                y_start = self.get_y()
                if y_start + row_height > self.page_break_trigger:
                    self.add_page()
                    draw_headers()
                    y_start = self.get_y()
                for header in headers_list:
                    x_start = self.get_x()
                    for i, line in enumerate(row_lines_dict[header]):
                        self.set_xy(x_start, y_start + i * line_height)
                        if header == 'Product Name':
                            link = product_links.get(line)  # Fetch link from dictionary
                            if link:
                                pdf_link = self.add_link()
                                self.set_link(pdf_link, page=self.page_no(), y=self.get_y())
                                self.set_text_color(0, 0, 255)
                                self.cell(cell_widths[header], line_height, line, 0, 0, 'C', link=link)
                                self.set_text_color(0)
                            else:
                                self.cell(cell_widths[header], line_height, line, 0, 0, 'C')  # No link if not found
                        else:
                            self.cell(cell_widths[header], line_height, line, 0, 0, 'C')
                        self.set_xy(x_start + cell_widths[header], y_start)

                self.set_y(y_start + row_height)
                self.set_y(y_start)
                x_start = self.l_margin
                for header in headers_list:
                    self.set_xy(x_start, y_start)
                    self.multi_cell(cell_widths[header], row_height, '', 1, 'C')
                    x_start += cell_widths[header]

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
            self.output(os.path.join(user_directory, 'table_of_contents.pdf'))

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
                self.cell(col_width, row_height, str(row[0]), 0, 0, 'L')
                x_chapter_end = self.get_x()
                self.cell(col_width, row_height, str(row[1]), 0, 0, 'L')
                x_brand_end = self.get_x()
                self.cell(col_width, row_height, str(row[2]), 0, 0, 'R')
                x_page_end = self.get_x()
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
    if filters.get('NoBackground'):
        toc_image = None
        content_image = None
    else:
        try:
            background_image = BackgroundImage.objects.first()
            toc_image = background_image.toc_image.path if background_image else None
            content_image = background_image.content_image.path if background_image else None
        except AttributeError:
            toc_image = None
            content_image = None

    # Create PDF for content with content background image
    pdf = PDF(orientation='L', background_image=content_image)
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

    content_pdf_output = os.path.join(user_directory, 'content.pdf')
    pdf.output(content_pdf_output)

    if not filters.get('NoTOC'):
        toc_temp = PDF(orientation='L')
        toc_temp.add_font('DejaVu', '', os.path.join(font_dir, 'DejaVuSans.ttf'), uni=True)
        toc_temp.add_font('DejaVu', 'B', os.path.join(font_dir, 'DejaVuSans-Bold.ttf'), uni=True)
        toc_temp.add_font('DejaVu', 'I', os.path.join(font_dir, 'DejaVuSans-Oblique.ttf'), uni=True)
        toc_temp.toc = pdf.toc
        toc_temp.add_toc_page()

        toc_temp_output = os.path.join(user_directory, 'toc_temp.pdf')
        toc_temp.output(toc_temp_output)

        toc_temp_reader = PdfReader(toc_temp_output)
        toc_pages_count = len(toc_temp_reader.pages)

        adjusted_toc = [(title, page + toc_pages_count, link) for title, page, link in pdf.toc]

        final_toc = PDF(orientation='L', background_image=toc_image)
        final_toc.add_font('DejaVu', '', os.path.join(font_dir, 'DejaVuSans.ttf'), uni=True)
        final_toc.add_font('DejaVu', 'B', os.path.join(font_dir, 'DejaVuSans-Bold.ttf'), uni=True)
        final_toc.add_font('DejaVu', 'I', os.path.join(font_dir, 'DejaVuSans-Oblique.ttf'), uni=True)
        final_toc.toc = adjusted_toc
        final_toc.add_toc_page()

        final_toc_output = os.path.join(user_directory, 'final_toc.pdf')
        final_toc.output(final_toc_output)

        final_toc_reader = PdfReader(final_toc_output)
        final_pdf_writer = PdfWriter()

        for page_num in range(len(final_toc_reader.pages)):
            final_pdf_writer.add_page(final_toc_reader.pages[page_num])

        content_pdf_reader = PdfReader(content_pdf_output)
        for page_num in range(len(content_pdf_reader.pages)):
            final_pdf_writer.add_page(content_pdf_reader.pages[page_num])

        final_output = os.path.join(user_directory, 'price_list_with_selling_prices.pdf')
        with open(final_output, 'wb') as f:
            final_pdf_writer.write(f)

        os.remove(content_pdf_output)
        os.remove(toc_temp_output)
        os.remove(final_toc_output)
    else:
        os.rename(content_pdf_output, os.path.join(user_directory, 'price_list_with_selling_prices.pdf'))

    excel_output = os.path.join(user_directory, 'price_list_with_selling_prices.xlsx')
    final_df.to_excel(excel_output, index=False)

    return redirect('results')

@login_required
def download_pdf(request):
    user_directory = os.path.join(output_dir, request.user.username)
    file_path = os.path.join(user_directory, 'price_list_with_selling_prices.pdf')
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), content_type='application/pdf', as_attachment=True, filename='price_list_with_selling_prices.pdf')
    return redirect('results')

@login_required
def download_pdf_promotion(request):
    file_path = os.path.join(output_dir, 'price_list_with_selling_prices.pdf')
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), content_type='application/pdf', as_attachment=True, filename='price_list_with_selling_prices.pdf')
    return redirect('promotion_results')

@login_required
def download_excel(request):
    user_directory = os.path.join(output_dir, request.user.username)
    file_path = os.path.join(user_directory, 'price_list_with_selling_prices.xlsx')
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, filename='price_list_with_selling_prices.xlsx')
    return redirect('results')

@login_required
def download_excel_promotion(request):
    file_path = os.path.join(output_dir, 'price_list_with_selling_prices.xlsx')
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, filename='price_list_with_selling_prices.xlsx')
    return redirect('promotion_results')

@login_required
def view_pdf(request):
    user_directory = os.path.join(output_dir, request.user.username)
    file_path = os.path.join(user_directory, 'price_list_with_selling_prices.pdf')
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), content_type='application/pdf')
    else:
        return HttpResponse("File not found", status=404)

@csrf_exempt
def update_csv_view(request):
    secure_token = 'iRQScq0YJtJxz8HQXYCORsh86OXQJcxt4BEmGXM5CTbM95ys6A'

    if request.method == 'POST':
        received_token = request.POST.get('token')
        file_name = request.headers.get('File-Name')  # Reading the file name from the header

        if received_token == secure_token:
            if not file_name:
                logger.error("No file name provided in the header")
                return HttpResponse("No file name provided in the header", status=400)

            data = request.POST.get('data')
            if not data:
                logger.error("No data provided")
                return HttpResponse("No data provided", status=400)

            try:
                df = pd.read_json(data)

                # Convert all strings in the dataframe to ASCII equivalents
                df = df.applymap(lambda x: unidecode(x) if isinstance(x, str) else x)

                csv_file_path = os.path.join(settings.BASE_DIR, 'data', file_name)
                df.to_csv(csv_file_path, index=False, encoding='latin-1')
                return HttpResponse(f'{file_name} updated successfully')
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

@login_required
def promotion_results(request):
    return render(request, 'price_list_app/promotion_results.html')

@login_required
def view_reservation_table(request):
    df = pd.read_csv(csv_file_path)

    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df[numeric_columns] = df[numeric_columns].fillna(0)

    nomenclature_mapping, _ = get_mappings()

    df['Group'] = df['nomenclature_group'].apply(lambda x: nomenclature_mapping.get(x[:3], 'Unknown'))

    # Filter the DataFrame to include only the specified columns
    df = df[['product_name', 'available', 'available_cz', 'brand', 'Group']]

    # Generate HTML tables for each brand
    brands = df['brand'].unique()
    brand_tables = {}
    for brand in brands:
        brand_df = df[df['brand'] == brand]
        brand_tables[brand] = brand_df.to_html(index=False, classes='table table-striped')

    return render(request, 'price_list_app/reservation_table.html', {'brand_tables': brand_tables})

@login_required
def generate_promotion_pricelist(request):
    try:
        # Load the necessary data from the database
        promotions = Promotion.objects.all()
        promotion_dict = {promo.product_name: promo.selling_price for promo in promotions}

        df = read_csv()

        # Filter the DataFrame to include only products in the Promotion model
        df = df[df['product_name'].isin(promotion_dict.keys())]

        # Adding the Promotion Price to the DataFrame
        df['Price'] = df['product_name'].map(promotion_dict)

        availability_column = 'available_cz'
        df = df[df[availability_column] > 0]

        grouped_df = df.groupby(['Group', 'brand', 'product_name'], as_index=False).agg({
            'available_cz': 'sum',
            'Price': 'max',
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

        final_columns = [
            'Group', 'brand', 'product_name', 'available_cz', 'delivery_month', 'delivery_cw',
            'panel_power', 'panel_colour', 'panel_design', 'length', 'width', 'height', 'pcs_pal', 'pcs_ctn', 'Price'
        ]

        final_df = grouped_df[final_columns]
        final_df = final_df.astype(str)
        empty_values = ['0', 'NaN', 'None', 'NULL', 'nan', '0.0']
        final_df.replace(empty_values, "", inplace=True)

        column_rename_dict = {
            'Group': 'Product Group',
            'brand': 'Brand',
            'product_name': 'Product Name',
            'available_cz': 'Available',
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
            'Price': 'Price'
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
            def __init__(self, orientation='P', background_image=None):
                super().__init__(orientation)
                self.background_image = background_image
                self.toc = []

            def header(self):
                if self.background_image:
                    self.image(self.background_image, x=0, y=0, w=self.w, h=self.h)
                self.set_font('DejaVu', 'B', 10)
                self.cell(0, 10, 'Price List', 0, 1, 'C')


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

            def add_table(self, dataframe, group):
                dataframe = dataframe.drop(columns=['Product Group', 'Brand'], errors='ignore')
                dataframe = dataframe.loc[:, ~(dataframe == "").all()]
                dataframe_copy = dataframe.copy()
                dataframe_copy.rename(columns={'Price': 'Price'}, inplace=True)

                self.set_font('DejaVu', 'B', 7)
                headers_list = dataframe_copy.columns.tolist()
                page_width = self.w - 2 * self.l_margin
                cell_widths = {}
                for header in headers_list:
                    max_content_width = max(self.get_string_width(str(value)) for value in dataframe_copy[header]) + 4
                    header_width = self.get_string_width(header.replace('_', ' ').title()) + 4
                    cell_widths[header] = max(max_content_width, header_width)
                if "Product Name" in cell_widths:
                    cell_widths["Product Name"] += 0.5 * self.get_string_width(' ')
                    cell_widths["Product Name"] += self.get_string_width(' ' * 3)
                total_width = sum(cell_widths.values())
                scale = page_width / total_width
                for header in cell_widths:
                    cell_widths[header] *= scale

                def split_text(text, cell_width, max_lines=2):
                    words = text.split(' ')
                    lines = []
                    current_line = words[0]
                    for word in words[1:]:
                        if self.get_string_width(current_line + ' ' + word) <= cell_width - 4:
                            current_line += ' ' + word
                        else:
                            lines.append(current_line)
                            current_line = word
                        if len(lines) >= max_lines - 1:
                            break
                    lines.append(current_line)
                    if len(lines) > max_lines:
                        lines = lines[:max_lines]
                    return lines

                max_lines = 2
                header_lines_dict = {}
                for header in headers_list:
                    header_lines = split_text(header.replace('_', ' ').title(), cell_widths[header], max_lines=max_lines)
                    header_lines_dict[header] = header_lines
                    max_lines = max(max_lines, len(header_lines))

                line_height = 5
                header_height = max_lines * line_height
                for header in headers_list:
                    if len(header_lines_dict[header]) > 1:
                        cell_widths[header] *= 0.8
                total_width = sum(cell_widths.values())
                scale = page_width / total_width
                for header in cell_widths:
                    cell_widths[header] *= scale

                def draw_headers():
                    y_start = self.get_y()
                    for header in headers_list:
                        x_start = self.get_x()
                        for i, line in enumerate(header_lines_dict[header]):
                            self.set_xy(x_start, y_start + i * line_height)
                            self.cell(cell_widths[header], line_height, line, 0, 0, 'C')
                        self.set_xy(x_start + cell_widths[header], y_start)
                    self.set_y(y_start + header_height)
                    self.set_y(y_start)
                    x_start = self.l_margin
                    for header in headers_list:
                        self.set_xy(x_start, y_start)
                        self.multi_cell(cell_widths[header], header_height, '', 1, 'C')
                        x_start += cell_widths[header]

                draw_headers()

                self.set_font('DejaVu', '', 7)
                for row in dataframe_copy.itertuples(index=False):
                    row_lines_dict = {}
                    max_row_lines = 1
                    for header in headers_list:
                        cell_text = str(row[headers_list.index(header)])
                        if header in ["Colour", "Product Name", "Design"]:
                            row_lines = split_text(cell_text, cell_widths[header], max_lines=2)
                        else:
                            row_lines = [cell_text]
                        row_lines_dict[header] = row_lines
                        max_row_lines = max(max_row_lines, len(row_lines))

                    row_height = max_row_lines * line_height
                    y_start = self.get_y()
                    if y_start + row_height > self.page_break_trigger:
                        self.add_page()
                        draw_headers()
                        y_start = self.get_y()
                    for header in headers_list:
                        x_start = self.get_x()
                        for i, line in enumerate(row_lines_dict[header]):
                            self.set_xy(x_start, y_start + i * line_height)
                            self.cell(cell_widths[header], line_height, line, 0, 0, 'C')
                        self.set_xy(x_start + cell_widths[header], y_start)

                    self.set_y(y_start + row_height)
                    self.set_y(y_start)
                    x_start = self.l_margin
                    for header in headers_list:
                        self.set_xy(x_start, y_start)
                        self.multi_cell(cell_widths[header], row_height, '', 1, 'C')
                        x_start += cell_widths[header]

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
                    self.cell(col_width, row_height, str(row[0]), 0, 0, 'L')
                    x_chapter_end = self.get_x()
                    self.cell(col_width, row_height, str(row[1]), 0, 0, 'L')
                    x_brand_end = self.get_x()
                    self.cell(col_width, row_height, str(row[2]), 0, 0, 'R')
                    x_page_end = self.get_x()
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

        try:
            background_image = BackgroundImage.objects.first()
            toc_image = background_image.toc_image.path if background_image else None
            content_image = background_image.content_image.path if background_image else None
        except AttributeError:
            toc_image = None
            content_image = None

        pdf = PDF(orientation='L', background_image=content_image)
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
                    pdf.add_table(brand_df, group)
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

        final_toc = PDF(orientation='L', background_image=toc_image)
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

        return redirect('promotion_results')

    except Exception as e:
        logger.error(f"Error generating promotion pricelist: {e}")
        return HttpResponse(f"Error generating promotion pricelist: {e}", status=500)
