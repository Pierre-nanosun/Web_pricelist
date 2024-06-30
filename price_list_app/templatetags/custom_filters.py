from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(bound_field, css_class):
    return bound_field.as_widget(attrs={"class": css_class})

@register.filter(name='get_bound_field')
def get_bound_field(form, field_name):
    return form[field_name]

@register.filter
def get_item(obj, key):
    try:
        return obj[key]
    except (KeyError, AttributeError, TypeError):
        return None

