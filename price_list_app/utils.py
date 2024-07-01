from .models import NomenclatureMapping, PanelMapping

def get_nomenclature_mapping():
    return {mapping.key: mapping.value for mapping in NomenclatureMapping.objects.all()}

def get_panel_mapping():
    return {mapping.key: mapping.value for mapping in PanelMapping.objects.all()}
