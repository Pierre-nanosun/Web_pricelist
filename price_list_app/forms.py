from django import forms
class SelectionForm(forms.Form):
    GROUP_CHOICES = [
        ('Panels', 'Panels'),
        ('Inverters', 'Inverters'),
        ('Batteries', 'Batteries'),
        ('EV Chargers', 'EV Chargers'),
        ('Accessories', 'Accessories'),
        ('Constructions', 'Constructions'),
        ('Portable Power Station', 'Portable Power Station'),
        ('Air Conditions', 'Air Conditions'),
        ('Heat Pumps', 'Heat Pumps'),
        ('SmartFlowers', 'SmartFlowers'),
        ('Cables', 'Cables')
    ]
    WAREHOUSE_CHOICES = [
        ('Decin', 'Decin'),
        ('Rotterdam', 'Rotterdam')
    ]
    NUM_PRICES_CHOICES = [(i, str(i)) for i in range(1, 5)]

    groups = forms.MultipleChoiceField(
        choices=GROUP_CHOICES,
        widget=forms.CheckboxSelectMultiple
    )
    warehouse = forms.ChoiceField(choices=WAREHOUSE_CHOICES)
    num_prices = forms.ChoiceField(choices=NUM_PRICES_CHOICES)

class CoefficientForm(forms.Form):
    def __init__(self, *args, **kwargs):
        groups = kwargs.pop('groups')
        num_prices = kwargs.pop('num_prices')
        default_config = kwargs.pop('default_config', {})
        warehouse = kwargs.pop('warehouse')
        super().__init__(*args, **kwargs)

        # Add debug statement
        print(f"Form initialization - default_config: {default_config}")

        for group in groups:
            for i in range(1, num_prices + 1):
                operation_key = f'{group}_operation_{i}'
                coeff_key = f'{group}_coefficient_{i}'
                header_key = f'{group}_header_{i}'

                operation_default = default_config.get(group, {}).get(f'operation_{i}', '*')
                coefficient_default = default_config.get(group, {}).get(f'coefficient_{i}', 1.2)
                header_default = default_config.get(group, {}).get(f'header_{i}', f'Price {i}')

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