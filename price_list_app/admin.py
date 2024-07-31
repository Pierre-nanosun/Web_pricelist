from django.contrib import admin
from .models import NomenclatureMapping, PanelMapping, Configuration, Brand, Logo, PriceLabel, Promotion, PanelColour, PanelDesign, BackgroundImage
from django import forms
from jsoneditor.forms import JSONEditor
from .views import upload_csv_view
from django.urls import path
from django.template.response import TemplateResponse

admin.site.register(NomenclatureMapping)
admin.site.register(PanelMapping)
admin.site.register(Brand)
admin.site.register(PanelColour)
admin.site.register(PanelDesign)

class PromotionAdmin(admin.ModelAdmin):
    change_list_template = "price_list_app/admin/promotion_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-csv/', self.admin_site.admin_view(self.upload_csv), name='upload_csv'),
        ]
        return custom_urls + urls

    def upload_csv(self, request):
        if request.method == "POST":
            return upload_csv_view(request)
        form = None  # Add your form logic here if needed
        context = {
            'form': form,
            'opts': self.model._meta,
            'title': "Import Promotions from CSV"
        }
        return TemplateResponse(request, "price_list_app/admin/upload_csv.html", context)

admin.site.register(Promotion, PromotionAdmin)

class ConfigurationAdminForm(forms.ModelForm):
    class Meta:
        model = Configuration
        fields = '__all__'
        widgets = {
            'coefficients': JSONEditor(attrs={'style': 'width: 800px;'}),
        }

@admin.register(BackgroundImage)
class BackgroundImageAdmin(admin.ModelAdmin):
    list_display = ('name', 'toc_image', 'content_image')

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



@admin.register(Logo)
class LogoAdmin(admin.ModelAdmin):
    list_display = ('name', 'file')


@admin.register(PriceLabel)
class PriceLabelAdmin(admin.ModelAdmin):
    list_display = ('product_group', 'price_label_1', 'price_label_2', 'price_label_3', 'price_label_4')
    search_fields = ('product_group',)