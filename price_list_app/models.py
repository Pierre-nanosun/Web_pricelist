from django.contrib.auth.models import User
from django.db import models

class Configuration(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    selected_groups = models.JSONField()
    warehouse = models.CharField(max_length=50)
    num_prices = models.IntegerField()
    coefficients = models.JSONField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, null=True)
    updated = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        unique_together = ('user', 'warehouse', 'selected_groups', 'num_prices')

    def __str__(self):
        return f"{self.user.username}: {self.warehouse}, {self.num_prices} Prices"
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