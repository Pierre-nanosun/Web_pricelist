from django.contrib.auth.models import User
from django.db import models

class Configuration(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    selected_groups = models.JSONField()
    warehouse = models.CharField(max_length=50)
    num_prices = models.IntegerField()
    coefficients = models.JSONField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, null=True)
    updated = models.DateTimeField(auto_now=True, null=True)
    selected_brands = models.JSONField(default=list)
    select_all_brands = models.BooleanField(default=False)
    filters = models.JSONField(null=True, blank=True)
    selected_columns = models.JSONField(default=list)
    def __str__(self):
        return f"{self.name} ({self.user.username}: {self.warehouse}, {self.num_prices} Prices)"

class BackgroundImage(models.Model):
    name = models.CharField(max_length=100)
    toc_image = models.ImageField(upload_to='backgrounds/toc/', default='backgrounds/default_toc.jpg')
    content_image = models.ImageField(upload_to='backgrounds/content/', default='backgrounds/default_content.jpg')

    def __str__(self):
        return self.name

class PanelColour(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class PanelDesign(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class NomenclatureMapping(models.Model):
    key = models.CharField(max_length=10, unique=True)
    value = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.key}: {self.value}"

class PanelMapping(models.Model):
    key = models.CharField(max_length=20, unique=True)
    value = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.key}: {self.value}"

class Brand(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Logo(models.Model):
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='logos/')

    def __str__(self):
        return self.name

class PriceLabel(models.Model):
    PRODUCT_GROUP_CHOICES = [
        ('Panels', 'Panels'),
        ('Other', 'Other'),
    ]

    OPERATION_CHOICES = [
        ('*', 'Multiplication'),
        ('+', 'Addition'),
    ]

    product_group = models.CharField(max_length=20, choices=PRODUCT_GROUP_CHOICES, unique=True)
    price_label_1 = models.CharField(max_length=100)
    price_label_2 = models.CharField(max_length=100)
    price_label_3 = models.CharField(max_length=100)
    price_label_4 = models.CharField(max_length=100)

    operation_1 = models.CharField(max_length=1, choices=OPERATION_CHOICES, default='*')
    operation_2 = models.CharField(max_length=1, choices=OPERATION_CHOICES, default='*')
    operation_3 = models.CharField(max_length=1, choices=OPERATION_CHOICES, default='*')
    operation_4 = models.CharField(max_length=1, choices=OPERATION_CHOICES, default='*')

    coefficient_1 = models.FloatField(default=1.0)
    coefficient_2 = models.FloatField(default=1.0)
    coefficient_3 = models.FloatField(default=1.0)
    coefficient_4 = models.FloatField(default=1.0)

    def __str__(self):
        return f"{self.get_product_group_display()} Price Labels"

class Promotion(models.Model):
    product_name = models.CharField(max_length=255)
    selling_price = models.FloatField()

    def __str__(self):
        return f"{self.product_name} - {self.selling_price}"
