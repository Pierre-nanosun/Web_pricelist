# forms.py

from django import forms
from .models import NomenclatureMapping, Brand

class SelectionForm(forms.Form):
    WAREHOUSE_CHOICES = [
        ('Decin', 'Decin'),
        ('Rotterdam', 'Rotterdam')
    ]
    NUM_PRICES_CHOICES = [(i, str(i)) for i in range(1, 5)]

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
        initial=Brand.objects.all()
    )

class CoefficientForm(forms.Form):
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
                coefficient_default = default_config.get(group, {}).get(f'coefficient_{i}', 1.2)
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
