from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True, null=True)

class Location(models.Model):
    name = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    # google_map_link = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    house_name = models.CharField(max_length=255, blank=True, null=True)
    photo = models.ImageField(upload_to="locations/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Order(models.Model):
    location = models.ForeignKey('Location', on_delete=models.CASCADE, related_name='orders')
    date = models.DateField()
    note = models.TextField(blank=True)
    photo = models.ImageField(upload_to="orders/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.pk} - {self.location.name} ({self.date})"