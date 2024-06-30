from django.contrib import admin
from .models import NomenclatureMapping, PanelMapping, Configuration
from django import forms
from jsoneditor.forms import JSONEditor

admin.site.register(NomenclatureMapping)
admin.site.register(PanelMapping)

class ConfigurationAdminForm(forms.ModelForm):
    class Meta:
        model = Configuration
        fields = '__all__'
        widgets = {
            'coefficients': JSONEditor(attrs={'style': 'width: 800px;'}),
        }

@admin.register(Configuration)
class ConfigurationAdmin(admin.ModelAdmin):
    form = ConfigurationAdminForm
    list_display = ('user', 'warehouse', 'num_prices', 'created', 'updated')
    search_fields = ('user__username', 'warehouse')
    list_filter = ('warehouse', 'num_prices')
    readonly_fields = ('created', 'updated')
    fieldsets = (
        (None, {
            'fields': ('user', 'selected_groups', 'warehouse', 'num_prices', 'coefficients')
        }),
    )

    def selected_groups_display(self, obj):
        return ', '.join(obj.selected_groups)
    selected_groups_display.short_description = 'Selected Groups'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
