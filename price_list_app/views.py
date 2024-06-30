# views.py
import os
import json
import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, login
from django.contrib.auth.forms import AuthenticationForm
from django.conf import settings
from django.http import FileResponse
from .forms import SelectionForm, CoefficientForm
from .models import Configuration
from fpdf import FPDF
from PyPDF2 import PdfReader, PdfWriter

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
nomenclature_mapping = {
    'PAN': 'Panels',
    'INV': 'Inverters',
    'BAT': 'Batteries',
    'EVC': 'EV Chargers',
    'ACC': 'Accessories',
    'CON': 'Constructions',
    'PPS': 'Portable Power Station',
    'ARC': 'Air Conditions',
    'HEP': 'Heat Pumps',
    'SMF': 'SmartFlowers',
    'CAB': 'Cables'
}
panel_mapping = {
    'GLASS': 'Glass foil',
    '2GLASS': 'Double glass',
    'BIF': 'Bifacial',
    'FLEXIBLE': 'Flexible',
    'GRID': 'Grid feed-in',
    'HYBRID': 'Hybrid',
    '3PH': 'Triple phase',
    '1PH': 'Single phase',
    'BF': 'Black Frame',
    'FB': 'Full Black',
    'FF_ANTHRACITE': 'Frameless Full Anthracite (G001)',
    'FF_BLACK': 'Frameless Full Black (B001)',
    'FF_BLUE': 'Frameless Full Blue (7003)',
    'FF_BRONZE': 'Frameless Full Bronze (3001)',
    'FF_DARK_BLUE': 'Frameless Full Dark blue (7002)',
    'FF_GOLD': 'Frameless Full Gold (3002)',
    'FF_GREEN': 'Frameless Full Green (4002)',
    'FF_GREY': 'Frameless Full Grey (G002)',
    'FF_LIGHT_BLUE': 'Frameless Full Light blue (7004)',
    'FF_LIGHT_GREEN': 'Frameless Full Light green (4001)',
    'FF_LIGHT_GREY': 'Frameless Full Light grey (G004)',
    'SF': 'Silver Frame'
}

def read_csv():
    df = pd.read_csv(csv_file_path)
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df[numeric_columns] = df[numeric_columns].fillna(0)
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
            selected_groups = form.cleaned_data['groups']
            warehouse = form.cleaned_data['warehouse']
            num_prices = form.cleaned_data['num_prices']
            config, created = Configuration.objects.get_or_create(
                user=request.user,
                selected_groups=json.dumps(selected_groups),
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

    # Add debug statement
    print(f"Raw config.coefficients: {config.coefficients}")

    try:
        default_config = json.loads(config.coefficients) if config.coefficients else {}
    except json.JSONDecodeError:
        default_config = {}

    # Add debug statement
    print(f"Parsed default_config: {default_config}")

    if request.method == 'POST':
        form = CoefficientForm(request.POST, groups=selected_groups, num_prices=num_prices,
                               default_config=default_config, warehouse=config.warehouse)
        if form.is_valid():
            coefficients = {}
            for group in selected_groups:
                coefficients[group] = {}
                for i in range(1, num_prices + 1):
                    coefficients[group][f'operation_{i}'] = form.cleaned_data[f'{group}_operation_{i}']
                    coefficients[group][f'coefficient_{i}'] = form.cleaned_data[f'{group}_coefficient_{i}']
                    coefficients[group][f'header_{i}'] = form.cleaned_data[f'{group}_header_{i}']
            # Add debug statement
            print(f"Saving coefficients: {coefficients}")
            config.coefficients = json.dumps(coefficients)
            config.save()
            return redirect('generate_files', config_id=config.id)
    else:
        form = CoefficientForm(groups=selected_groups, num_prices=num_prices, default_config=default_config,
                               warehouse=config.warehouse)

    dynamic_fields = [
        {
            "group": group,
            "fields": [
                {
                    "operation": f"{group}_operation_{i}",
                    "coefficient": f"{group}_coefficient_{i}",
                    "header": f"{group}_header_{i}"
                } for i in range(1, num_prices + 1)
            ]
        } for group in selected_groups
    ]

    return render(request, 'price_list_app/input_coefficients.html',
                  {'form': form, 'num_prices_range': range(1, num_prices + 1), 'dynamic_fields': dynamic_fields})
@login_required
def generate_files(request, config_id):
    config = get_object_or_404(Configuration, id=config_id)
    selected_groups = json.loads(config.selected_groups)
    warehouse = config.warehouse
    num_prices = config.num_prices
    coefficients = json.loads(config.coefficients)

    df = read_csv()
    df = df[df['Group'].isin(selected_groups)]

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
            op = coefficients[group][f'operation_{j}']
            coeff = coefficients[group][f'coefficient_{j}']
            header = coefficients[group][f'header_{j}']
            price = calculate_selling_price(bp_price, op, coeff)
            row[f'Price {j}'] = round(price, 3) if group == 'Panels' else round(price, 0)
        return row

    df = df.apply(apply_coefficients, axis=1)

    for j in range(1, num_prices + 1):
        price_col = f'Price {j}'
        if price_col not in df.columns:
            df[price_col] = 0

    availability_column = 'available_cz' if warehouse == 'Decin' else 'available'
    df = df[df[availability_column] > 0]

    grouped_df = df.groupby(['Group', 'brand', 'product_name'], as_index=False).agg({
        'available': 'sum',
        'available_cz': 'sum',
        'bp_eur': 'max',
        'bp_eur_cz': 'max',
        **{f'Price {j}': 'max' for j in range(1, num_prices + 1)},
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
    custom_order = list(nomenclature_mapping.values())
    grouped_df['Group'] = pd.Categorical(grouped_df['Group'], categories=custom_order, ordered=True)
    grouped_df = grouped_df.sort_values('Group').reset_index(drop=True)

    final_columns = [
        'Group', 'brand', 'product_name', 'available', 'delivery_month', 'delivery_cw',
        'panel_power', 'panel_colour', 'panel_design', 'length', 'width', 'height', 'pcs_pal', 'pcs_ctn',
        *[f'Price {j}' for j in range(1, num_prices + 1)]
    ]
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
        **{f'Price {j}': coefficients[selected_groups[0]][f'header_{j}'] for j in range(1, num_prices + 1)}
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

    logo_dict = {}
    image_extensions = ['.jpeg', '.png', '.jpg']
    logo_files = [file for file in os.listdir(logos_dir) if os.path.splitext(file)[1].lower() in image_extensions]
    for logo in logo_files:
        logo_dict[os.path.splitext(logo)[0]] = os.path.join(logos_dir, logo)

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
                    self.image(logo_path, x=12, y=self.get_y(), h=height)
            else:
                logo_path = logo_dict["NANOSUN"]
                if os.path.isfile(logo_path):
                    self.image(logo_path, x=12, y=self.get_y(), h=height)
            self.ln(height)

        def add_table(self, dataframe):
            dataframe = dataframe.drop(columns=['Product Group', 'Brand'], errors='ignore')
            dataframe = dataframe.loc[:, ~(dataframe == "").all()]

            self.set_font('DejaVu', 'B', 7)
            headers = dataframe.columns.tolist()
            page_width = self.w - 2 * self.l_margin
            cell_widths = {header: self.get_string_width(header) + 2 for header in headers}

            for header in headers:
                for value in dataframe[header]:
                    cell_widths[header] = max(cell_widths[header], self.get_string_width(str(value)) + 2)
            cell_widths['Product Name'] = max(cell_widths['Product Name'], 50)
            total_width = sum(cell_widths.values())
            scale = page_width / total_width
            for header in cell_widths:
                cell_widths[header] *= scale

            for header in headers:
                self.cell(cell_widths[header], 10, header.replace('_', ' ').title(), 1, 0, 'C')
            self.ln()

            self.set_font('DejaVu', '', 7)
            for row in dataframe.itertuples(index=False):
                for header in headers:
                    self.cell(cell_widths[header], 10, str(row[headers.index(header)]), 1, 0)
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
                pdf.add_table(brand_df)
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

def results(request):
    return render(request, 'price_list_app/results.html')

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
    return redirect('results')
