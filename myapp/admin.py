from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Location,User, Pickup, PickupItem, Item, Employee
admin.site.register(User,UserAdmin)
admin.site.register(Location)
admin.site.register(Pickup)
admin.site.register(PickupItem)
admin.site.register(Item)
admin.site.register(Employee)