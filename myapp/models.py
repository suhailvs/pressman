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

    PAYMENT_UPI = "upi"
    PAYMENT_CASH = "cash"
    PAYMENT_CHOICES = [
        (PAYMENT_UPI, "UPI"),
        (PAYMENT_CASH, "Cash"),
    ]

    location = models.ForeignKey("Location", on_delete=models.CASCADE, related_name="pickups")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    picked_up_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    note = models.TextField(blank=True)
    photo = models.ImageField(upload_to="pickups/", blank=True, null=True)

    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, blank=True, null=True)
    amount_paid = models.IntegerField(blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    def __str__(self):
        return f"{self.location.name} — {self.get_status_display()}"

    @property
    def items_total(self):
        return sum(pi.total for pi in self.items.all())

    @property
    def is_paid(self):
        return self.paid_at is not None
 

class Item(models.Model):
    CATEGORY_DRYCLEANING = "d"
    CATEGORY_IRONING = "i"
    CATEGORY_CHOICES = [
        (CATEGORY_DRYCLEANING, "Drycleaning"),
        (CATEGORY_IRONING, "Ironing"),
    ]

    name = models.CharField(max_length=255)
    item_category = models.CharField(max_length=1, choices=CATEGORY_CHOICES, default=CATEGORY_DRYCLEANING)
    price = models.IntegerField(default=0)

    class Meta:
        ordering = ["name", "item_category"]
        unique_together = ("name", "item_category")

    def __str__(self):
        return f"{self.name} ({self.get_item_category_display()})"
 
 
class PickupItem(models.Model):
    pickup = models.ForeignKey(Pickup, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="pickup_items")
    quantity = models.PositiveIntegerField(default=1)
    price = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
 
    @property
    def total(self):
        return self.price * self.quantity
 
    def __str__(self):
        return f"{self.quantity} x {self.item.name}"