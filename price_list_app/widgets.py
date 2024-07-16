from django import forms

class MonthYearWidget(forms.MultiWidget):
    def __init__(self, attrs=None):
        months = [(None, 'Month')] + [(i, i) for i in range(1, 13)]
        years = [(None, 'Year')] + [(i, i) for i in range(2024, 2031)]
        widgets = [forms.Select(attrs=attrs, choices=months), forms.Select(attrs=attrs, choices=years)]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return value.split('-')
        return [None, None]

    def format_output(self, rendered_widgets):
        return '%s / %s' % (rendered_widgets[0], rendered_widgets[1])

    def value_from_datadict(self, data, files, name):
        month = data.get('%s_0' % name)
        year = data.get('%s_1' % name)
        if month and year:
            return f'{year}-{int(month):02d}'
        return None