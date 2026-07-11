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


class Pickup(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PICKED_UP = "picked_up"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"
 
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PICKED_UP, "Picked Up"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_CANCELLED, "Cancelled"),
    ]
 
    location = models.ForeignKey("Location", on_delete=models.CASCADE, related_name="pickups")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    picked_up_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    note = models.TextField(blank=True)
    photo = models.ImageField(upload_to="pickups/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    def __str__(self):
        return f"{self.location.name} — {self.get_status_display()}"