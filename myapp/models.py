from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from simple_history.models import HistoricalRecords
class GeneralSettings(models.Model):
    key = models.CharField(max_length=50)
    value = models.CharField(max_length=250)
    history = HistoricalRecords()
    def __str__(self) -> str:
        return f"{self.id}: {self.key}:{self.value}"
    
class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True, null=True)
    history = HistoricalRecords()
    def __str__(self):
        return self.first_name
    
class Location(models.Model):
    name = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    # google_map_link = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    house_name = models.CharField(max_length=255, blank=True, null=True)
    photo = models.ImageField(upload_to="locations/", blank=True, null=True)
    balance = models.IntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()
    def __str__(self):
        return self.name

class Pickup(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PICKED_UP = "picked_up"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"
    STATUS_FINISHED = "finished"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PICKED_UP, "Picked Up"),
        (STATUS_FINISHED, "Finished"),
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
    history = HistoricalRecords()
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
    history = HistoricalRecords()
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
    history = HistoricalRecords()
 
    @property
    def total(self):
        return self.price * self.quantity
 
    def __str__(self):
        return f"{self.quantity} x {self.item.name}"
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["pickup", "item"], name="unique_pickup_item")
        ]

class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # name = models.CharField(max_length=100)
    daily_wage = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    history = HistoricalRecords()
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.user.username})"
 
class Advance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='advances')
    amount = models.PositiveIntegerField()
    date = models.DateField(default=timezone.localdate)
    note = models.CharField(max_length=200, blank=True)
    approved = models.BooleanField(default=False)
    history = HistoricalRecords()
    def __str__(self):
        return f"{self.employee.user.get_full_name()} - {self.amount} on {self.date}"

class Expense(models.Model):
    CATEGORY_TEA = "tea"    
    CATEGORY_ELECTRICITY = "electricity"
    CATEGORY_RENT = "rent"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        (CATEGORY_TEA, "Tea"),
        (CATEGORY_ELECTRICITY, "Electricity"),
        (CATEGORY_RENT, "Rent"),
        (CATEGORY_OTHER, "Other"),
    ]

    date = models.DateField(default=timezone.localdate)
    amount = models.PositiveIntegerField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    note = models.CharField(max_length=200, blank=True)
    # Leave both blank for a normal same-day expense. Fill these in for
    # periodic bills (e.g. rent for a month, electricity for two months)
    # so the expense can be attributed to the period it actually covers,
    # not just the day it was paid.
    period_start = models.DateField(blank=True, null=True)
    period_end = models.DateField(blank=True, null=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.get_category_display()} - {self.amount} on {self.date}"

    @property
    def covers_period(self):
        """True if this expense is tied to a date range rather than a single day."""
        return bool(self.period_start and self.period_end)

    @property
    def period_label(self):
        if not self.covers_period:
            return None
        if self.period_start.strftime("%b %Y") == self.period_end.strftime("%b %Y"):
            return self.period_start.strftime("%b %Y")
        return f"{self.period_start.strftime('%b %Y')} – {self.period_end.strftime('%b %Y')}"
    
class Attendance(models.Model):
    DAY_TYPE_CHOICES = [('full', 'Full Day'), ('half', 'Half Day')]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance')
    date = models.DateField(default=timezone.localdate)
    day_type = models.CharField(max_length=4, choices=DAY_TYPE_CHOICES, default='full')
    marked_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()
    
    class Meta:
        unique_together = ('employee', 'date')
    def __str__(self):
        return f"{self.employee.user.get_full_name()} - {self.date} ({self.day_type})"

