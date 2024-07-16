from django import forms
from .models import NomenclatureMapping, Brand, Configuration, PanelColour, PanelDesign, BackgroundImage
from .widgets import MonthYearWidget
from datetime import datetime


class BackgroundImageForm(forms.ModelForm):
    class Meta:
        model = BackgroundImage
        fields = ['name', 'toc_image', 'content_image']

class SelectionForm(forms.Form):
    WAREHOUSE_CHOICES = [
        ('Decin', 'Decin'),
        ('Rotterdam', 'Rotterdam')
    ]
    NUM_PRICES_CHOICES = [(i, str(i)) for i in range(0, 5)]

    COLUMN_CHOICES = [
        ('available', 'Available'),
        ('delivery_month', 'Delivery Month'),
        ('delivery_cw', 'Delivery CW'),
        ('panel_power', 'Power(W)'),
        ('panel_colour', 'Colour'),
        ('panel_design', 'Design'),
        ('length', 'Length'),
        ('width', 'Width'),
        ('height', 'Height'),
        ('pcs_pal', 'Pcs Pal'),
        ('pcs_ctn', 'Pcs Ctn'),
    ]

    groups = forms.ModelMultipleChoiceField(
        queryset=NomenclatureMapping.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label='Product Types'
    )
    warehouse = forms.ChoiceField(choices=WAREHOUSE_CHOICES, label='Warehouse')
    num_prices = forms.ChoiceField(choices=NUM_PRICES_CHOICES, label='Number of Prices')
    brands = forms.ModelMultipleChoiceField(
        queryset=Brand.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label='Brands',
        required=False
    )
    select_all_brands = forms.BooleanField(required=False, initial=True, label='Select All Brands')

    selected_columns = forms.MultipleChoiceField(
        choices=COLUMN_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label='Columns to Display'
    )
    configurations = forms.ModelChoiceField(
        queryset=Configuration.objects.none(),
        required=False,
        label='Saved Configurations'
    )

    delivery_month_start = forms.CharField(widget=MonthYearWidget(), required=False, label='Delivery Month Start', initial=None)
    delivery_month_end = forms.CharField(widget=MonthYearWidget(), required=False, label='Delivery Month End', initial=None)
    panel_power_min = forms.FloatField(required=False, label='Minimum Power (W)')
    panel_power_max = forms.FloatField(required=False, label='Maximum Power (W)')
    panel_colour = forms.ModelMultipleChoiceField(queryset=PanelColour.objects.all(), required=False, label='Panel Colour', widget=forms.CheckboxSelectMultiple)
    panel_design = forms.ModelMultipleChoiceField(queryset=PanelDesign.objects.all(), required=False, label='Panel Design', widget=forms.CheckboxSelectMultiple)
    length_min = forms.FloatField(required=False, label='Minimum Length (mm)')
    length_max = forms.FloatField(required=False, label='Maximum Length (mm)')
    height_min = forms.FloatField(required=False, label='Minimum Height (mm)')
    height_max = forms.FloatField(required=False, label='Maximum Height (mm)')
    width_min = forms.FloatField(required=False, label='Minimum Width (mm)')
    width_max = forms.FloatField(required=False, label='Maximum Width (mm)')
    available = forms.IntegerField(required=False, label='Available')
    power_available = forms.IntegerField(required=False, label='Power Available (W)')
    NoBackground = forms.BooleanField(required=False, label='No Background')
    length_height_limit = forms.BooleanField(required=False, label='Length * Height <= 2000')
    no_delivery_date = forms.BooleanField(required=False, label='No Delivery Date')

    def clean_delivery_month_start(self):
        delivery_month_start = self.cleaned_data.get('delivery_month_start')
        if delivery_month_start:
            try:
                return datetime.strptime(delivery_month_start, '%Y-%m')
            except ValueError:
                raise forms.ValidationError("Invalid date format for delivery month start")
        return None

    def clean_delivery_month_end(self):
        delivery_month_end = self.cleaned_data.get('delivery_month_end')
        if delivery_month_end:
            try:
                return datetime.strptime(delivery_month_end, '%Y-%m')
            except ValueError:
                raise forms.ValidationError("Invalid date format for delivery month end")
        return None

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['configurations'].queryset = Configuration.objects.filter(user=user)
        self.fields['selected_columns'].initial = [choice[0] for choice in self.COLUMN_CHOICES]

class CoefficientForm(forms.Form):
    name = forms.CharField(max_length=100, required=True, label="Configuration Name")

    def __init__(self, *args, **kwargs):
        groups = kwargs.pop('groups')
        num_prices = kwargs.pop('num_prices')
        default_config = kwargs.pop('default_config', {})
        pricelabel_headers = kwargs.pop('pricelabel_headers', {})
        warehouse = kwargs.pop('warehouse')
        super().__init__(*args, **kwargs)

        for group in groups:
            for i in range(1, num_prices + 1):
                operation_key = f'{group}_operation_{i}'
                coeff_key = f'{group}_coefficient_{i}'
                header_key = f'{group}_header_{i}'

                operation_default = default_config.get(group, {}).get(f'operation_{i}', '*')
                coefficient_default = default_config.get(group, {}).get(f'coefficient_{i}', 1.0)
                header_default = default_config.get(group, {}).get(f'header_{i}', pricelabel_headers.get(group, {}).get(f'price_label_{i}', pricelabel_headers.get('Other', {}).get(f'price_label_{i}', f'price_label_{i}')))

                self.fields[operation_key] = forms.ChoiceField(
                    choices=[('*', '*'), ('+', '+')],
                    initial=operation_default,
                    widget=forms.Select(attrs={'class': 'form-control'})
                )
                self.fields[coeff_key] = forms.FloatField(
                    initial=coefficient_default,
                    widget=forms.NumberInput(attrs={'class': 'form-control'})
                )
                self.fields[header_key] = forms.CharField(
                    initial=header_default,
                    widget=forms.TextInput(attrs={'class': 'form-control'})
                )
