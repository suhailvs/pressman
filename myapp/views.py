import requests
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

from .forms import LocationForm,PickupForm
from .models import Location,Pickup, PickupItem, Item


@login_required
def home(request):
    locations = Location.objects.filter(is_active=True).order_by("name")
    return render(request, "locations/location_list.html", {"locations": locations})

class LocationsLoginView(LoginView):
    template_name = "locations/login.html"
    redirect_authenticated_user = True

@login_required
def location_create(request):
    if request.method == "POST":
        form = LocationForm(request.POST, request.FILES)
        if form.is_valid():
            location = form.save()
            messages.success(request, f'"{location.name}" was added.')
            return redirect("location_list")
    else:
        form = LocationForm()
    return render(request, "locations/add_location.html", {"form": form})

@login_required
def location_detail(request, pk):
    location = get_object_or_404(Location, pk=pk)

    if request.method == "POST" and request.POST.get("_method") == "delete":
        location.is_active = False # location.delete()
        location.save()
        messages.success(request, f'"{location.name}" was deactivated.')
        return redirect("location_list")

    return render(request, "locations/view_location.html", {"location": location})

@login_required
def location_edit(request, pk):
    location = get_object_or_404(Location, pk=pk)

    if request.method == "POST":
        form = LocationForm(request.POST, request.FILES, instance=location)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{location.name}" was updated.')
            return redirect("location_detail", pk=location.pk)
    else:
        form = LocationForm(instance=location)

    return render(
        request, "locations/edit_location.html", {"form": form, "location": location}
    )

@login_required
def location_map(request):
    locations = Location.objects.filter(is_active=True).exclude(latitude__isnull=True).exclude(longitude__isnull=True)
    return render(request, "locations/location_map.html", {"locations": locations})

@login_required
def location_pickups(request, pk):
    location = get_object_or_404(Location, pk=pk)
 
    if request.method == "POST":
        form = PickupForm(request.POST, request.FILES)
        if form.is_valid():
            pickup = form.save(commit=False)
            pickup.location = location
            pickup.save()
            messages.success(request, "Pickup added.")
            return redirect("location_pickups", pk=location.pk)
        show_add_modal = True
    else:
        form = PickupForm()
        show_add_modal = False
 
    pickups = location.pickups.all().order_by("-created_at")
 
    return render(request, "locations/pickup_list.html", {
        "location": location,
        "pickups": pickups,
        "form": form,
        "show_add_modal": show_add_modal,
    })

def pickup_detail(request, pk):
    pickup = get_object_or_404(Pickup, pk=pk)

    if request.method == "POST":
        if request.POST.get("_method") == "delete":
            location_pk = pickup.location.pk
            pickup.delete()
            messages.success(request, "Pickup deleted.")
            return redirect("location_detail", pk=location_pk)

        form = PickupForm(request.POST, request.FILES, instance=pickup)
        if form.is_valid():
            form.save()
            messages.success(request, "Pickup updated.")
            return redirect("pickup_detail", pk=pickup.pk)
        show_edit_modal = True
    else:
        form = PickupForm(instance=pickup)
        show_edit_modal = False

    return render(request, "locations/pickup_detail.html", {
        "pickup": pickup,
        "location": pickup.location,
        "form": form,
        "show_edit_modal": show_edit_modal,
        "dry_items": Item.objects.filter(item_category=Item.CATEGORY_DRYCLEANING),
        "iron_items": Item.objects.filter(item_category=Item.CATEGORY_IRONING),
        "pickup_items": pickup.items.select_related("item").all(),
    })
 
@login_required
def add_pickup_items(request, pk):
    pickup = get_object_or_404(Pickup, pk=pk)
    item_names = request.POST.getlist("item_name")
    quantities = request.POST.getlist("quantity")
    prices = request.POST.getlist("price")
    category = request.POST.get("item_category")
    if category not in (Item.CATEGORY_DRYCLEANING, Item.CATEGORY_IRONING):
        category = Item.CATEGORY_DRYCLEANING

    created = 0
    for raw_name, raw_qty, raw_price in zip(item_names, quantities, prices):
        name = raw_name.strip().lower()
        if not name:
            continue
        try:
            quantity = max(1, int(raw_qty))
        except (TypeError, ValueError):
            quantity = 1

        raw_price = (raw_price or "").strip()
        if raw_price:
            try:
                price = int(raw_price)
            except ValueError:
                price = 0
        else:
            price = 0

        item, _ = Item.objects.get_or_create(name=name, item_category=category, defaults={"price": price})
        if not raw_price:
            price = item.price
        PickupItem.objects.create(pickup=pickup, item=item, quantity=quantity, price=price)
        created += 1

    if created:
        messages.success(request, f"Added {created} item{'s' if created != 1 else ''}.")
    else:
        messages.error(request, "No items were entered.")

    return redirect("pickup_detail", pk=pickup.pk)
 
 
@login_required
def remove_pickup_item(request, pk):
    pickup_item = get_object_or_404(PickupItem, pk=pk)
    pickup_pk = pickup_item.pickup.pk
    pickup_item.delete()
    messages.success(request, "Item removed.")
    return redirect("pickup_detail", pk=pickup_pk)
 
@login_required
def mark_pickup_paid(request, pk):
    pickup = get_object_or_404(Pickup, pk=pk)
    if request.method == "POST":
        method = request.POST.get("payment_method")
        amount = (request.POST.get("amount") or "").strip()
        try:
            amount = int(float(amount)) if amount else None
        except ValueError:
            amount = None
        if method in (Pickup.PAYMENT_UPI, Pickup.PAYMENT_CASH) and amount is not None:
            pickup.payment_method = method
            pickup.amount_paid = amount
            pickup.paid_at = timezone.now()
            pickup.save()
            messages.success(request, f"Marked paid via {pickup.get_payment_method_display()}.")
        else:
            messages.error(request, "Select a payment method and enter a valid amount.")
    return redirect("pickup_detail", pk=pickup.pk)

@login_required
def all_pickups(request):
    show_all = request.GET.get("show_all") == "1" 
    pickups_qs = Pickup.objects.select_related("location").all().order_by("-created_at")
    if not show_all:
        pickups_qs = pickups_qs.exclude(status=Pickup.STATUS_DELIVERED) 
    paginator = Paginator(pickups_qs, 50)
    page_obj = paginator.get_page(request.GET.get("page")) 
    return render(request, "locations/all_pickups.html", {"pickups": page_obj,"page_obj": page_obj,"show_all": show_all})

@login_required
def quick_add_pickup(request, pk):
    location = get_object_or_404(Location, pk=pk)
    pickup = Pickup.objects.create(location=location)
    # detail_url = request.build_absolute_uri(reverse("pickup_detail", kwargs={"pk": pickup.pk}))
    # telegram bot see: https://github.com/suhailvs-archive/stack/blob/main/backend/api/views.py
    TELEGRAM_BOT_TOKEN = "8574559583:AAG7tRjCSCbW4DkQx3P4a3X44Wp9Ba7RKB4"    
    text = (
        f"📦 *New Pickup Created*\n"
        f"📍 *Location:* {location.name}\n"
        f"🏠 {location.house_name or '—'}\n"        
        f"🕐 {timezone.localtime(pickup.created_at).strftime('%b %d, %Y · %I:%M %p')}\n\n"
        f"[View on GoogleMap](https://www.google.com/maps?q={ location.latitude },{ location.longitude })"
        # f"[View pickup]({detail_url})"
    ) 
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={'chat_id':-5579934168, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True},
            timeout=5,
        )
    except requests.RequestException:
        pass
    messages.success(request, "Pickup created.")
    return redirect("all_pickups")

@login_required
def set_pickup_status(request, pk, status):
    if status not in (Pickup.STATUS_PICKED_UP, Pickup.STATUS_DELIVERED):
        return redirect(request.META.get("HTTP_REFERER", "all_pickups"))
 
    pickup = get_object_or_404(Pickup, pk=pk)
    pickup.status = status
 
    now = timezone.now()
    if status == Pickup.STATUS_PICKED_UP and not pickup.picked_up_at:
        pickup.picked_up_at = now
    elif status == Pickup.STATUS_DELIVERED and not pickup.delivered_at:
        pickup.delivered_at = now
 
    pickup.save()
    messages.success(request, f"Marked as {pickup.get_status_display()}.")
    return redirect(request.META.get("HTTP_REFERER", "all_pickups"))

# @login_required
def backup_media(request):
    import zipfile
    from datetime import datetime
    from django.http import FileResponse, JsonResponse
    from django.conf import settings
    import os
    
    media_root = settings.MEDIA_ROOT
    backup_dir = os.path.join(settings.BASE_DIR,"mysite", "backups")
    os.makedirs(backup_dir, exist_ok=True)

    # Delete existing zip files in backups folder
    for f in os.listdir(backup_dir):
        if f.endswith(".zip"): os.remove(os.path.join(backup_dir, f))
    timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
    zip_name  = f"media_backup_{timestamp}.zip"
    zip_path  = os.path.join(backup_dir, zip_name)

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(media_root):
                for file in files:
                    abs_path = os.path.join(root, file)
                    arc_path = os.path.relpath(abs_path, media_root)
                    zf.write(abs_path, arc_path)

        # Stream the file to browser without loading into RAM
        response = FileResponse(
            open(zip_path, "rb"),
            content_type="application/zip",
            as_attachment=True,
            filename=zip_name,
        )
        return response

    except Exception as e:
        return JsonResponse({"Error":f"Error: {e}"})