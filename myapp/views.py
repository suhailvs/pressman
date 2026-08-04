import re
import calendar
import requests
from itertools import groupby
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from datetime import date,time

from .forms import LocationForm,PickupForm
from .models import Location,Pickup, PickupItem, Item, Employee, Attendance, Advance

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
    pickups = location.pickups.exclude(status=Pickup.STATUS_CANCELLED).order_by("-created_at")
    return render(request, "locations/view_location.html", {"location": location,"pickups": pickups})

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
def pickup_detail(request, pk):
    pickup = get_object_or_404(Pickup, pk=pk)

    if request.method == "POST":
        if request.POST.get("_method") == "delete":
            location_pk = pickup.location.pk
            pickup.status=Pickup.STATUS_CANCELLED
            pickup.save()
            messages.success(request, "Pickup cancelled.")
            return redirect("all_pickups")

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
def create_item(request):
    pickup_pk = request.POST["pickup_pk"] # used to redirect back to the pickup detail page
    name = re.sub(r"\s+","_",request.POST["name"].strip().lower())
    category = request.POST["item_category"]
    if Item.objects.filter( name=name, item_category=category).exists():
        messages.error(request, "Item already exists.")
        return redirect("pickup_detail", pk=pickup_pk)
    Item.objects.create(name=name,item_category=category,price=int(request.POST["price"]))
    messages.success(request, "Item created.")
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


def _date_group_label(d, today):
    delta = (today - d).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    if 2 <= delta <= 6:
        return d.strftime("%A")  # e.g. "Sunday"
    return d.strftime("%b %d, %Y")  # e.g. "Jul 28, 2026"

@login_required
def all_pickups(request):
    show_all = request.GET.get("show_all") == "1"
    pickups_qs = (
        Pickup.objects.select_related("location")
        .exclude(status=Pickup.STATUS_CANCELLED)
        .order_by("-created_at")
    )
    if not show_all:
        pickups_qs = pickups_qs.exclude(status=Pickup.STATUS_DELIVERED)

    paginator = Paginator(pickups_qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    today = timezone.localdate()
    grouped_pickups = [
        {"label": _date_group_label(created_date, today), "pickups": list(items)}
        for created_date, items in groupby(
            page_obj.object_list,
            key=lambda p: timezone.localtime(p.created_at).date(),
        )
    ]

    return render(request, "locations/all_pickups.html", {
        "pickups": page_obj,
        "page_obj": page_obj,
        "show_all": show_all,
        "grouped_pickups": grouped_pickups,
    })
    
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


# Cycled avatar colors so each employee gets a stable-ish color by id.
AVATAR_COLORS = ['#128C7E', '#3A7CA5', '#C0533A', '#6B4FA8', '#B8860B', '#4C7A3D']
 
 
def _avatar_color(employee_id):
    return AVATAR_COLORS[employee_id % len(AVATAR_COLORS)]
 
@login_required 
def staff_list(request):
    today = timezone.localdate()
    employees = Employee.objects.filter(is_active=True).order_by('user__first_name')
 
    todays_attendance = {
        a.employee_id: a
        for a in Attendance.objects.filter(employee__in=employees, date=today)
    }
 
    staff_today = []
    for emp in employees:
        att = todays_attendance.get(emp.id)
        staff_today.append({
            'id': emp.id,
            'name': emp.user.get_full_name() or emp.user.username,
            'color': _avatar_color(emp.id),
            'marked_time': timezone.localtime(att.marked_at).strftime('%-I:%M %p') if att else None,
            'status': att.day_type if att else 'pending',
        })
 
    month_start = today.replace(day=1)
    month_attendance = Attendance.objects.filter(
        employee__in=employees, date__gte=month_start, date__lte=today,
    )
    month_advances = Advance.objects.filter(
        employee__in=employees, date__gte=month_start, date__lte=today,
    )
 
    full_counts, half_counts = {}, {}
    for a in month_attendance:
        bucket = full_counts if a.day_type == 'full' else half_counts
        bucket[a.employee_id] = bucket.get(a.employee_id, 0) + 1
 
    advance_totals = {}
    for adv in month_advances:
        advance_totals[adv.employee_id] = advance_totals.get(adv.employee_id, 0) + adv.amount
 
    staff_month = []
    for emp in employees:
        full_days = full_counts.get(emp.id, 0)
        half_days = half_counts.get(emp.id, 0)
        advance = advance_totals.get(emp.id, 0)
        # round() handles odd daily_wage * half-day (e.g. 501 wage -> 250.5 -> 251)
        earned = round(emp.daily_wage * (full_days + 0.5 * half_days))
        staff_month.append({
            'id': emp.id,
            'name': emp.user.get_full_name() or emp.user.username,
            'color': _avatar_color(emp.id),
            'full_days': full_days,
            'half_days': half_days,
            'advance': advance,
            'net': earned - advance,
        })
 
    return render(request, 'locations/staff_list.html', {
        'staff_today': staff_today,
        'staff_month': staff_month,
        'today': today,
    })
 
@login_required
def mark_attendance(request):
    if not (time(8, 0) <= timezone.localtime().time() <= time(20, 0)):
        messages.error(request, 'You can only mark attendance between 8:00 AM and 8:00 PM.')
        return redirect('staff_list')
    employee = request.user.employee
    day_type = request.GET.get('day_type', 'full')
    obj, created = Attendance.objects.get_or_create(
        employee=employee,
        date=timezone.localdate(),
        defaults={'day_type': day_type}
    )
    if not created:
        messages.error(request, 'Already marked for today')
        return redirect('staff_list')
    label = 'Full day' if day_type == 'full' else 'Half day'
    messages.success(request, f'Marked {employee.name} as {label}.')
    return redirect('staff_list')

@login_required
def add_advance(request):
    if request.method == "POST":
        employee = request.user.employee
        amount = request.POST.get("amount", "").strip()
        note = request.POST.get("note", "").strip()
        Advance.objects.create(employee=employee, amount=amount, note=note)
        return redirect('staff_list')
    return render(request, "locations/add_advance.html")



@login_required
def staff_detail(request, pk):
    employee = get_object_or_404(Employee, pk=pk)

    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except ValueError:
        year, month = today.year, today.month

    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    attendance_qs = employee.attendance.filter(date__range=(first_day, last_day)).order_by('date')
    advances_qs = employee.advances.filter(date__range=(first_day, last_day)).order_by('-date')

    full_days = attendance_qs.filter(day_type='full').count()
    half_days = attendance_qs.filter(day_type='half').count()

    earned = (full_days * employee.daily_wage) + (half_days * employee.daily_wage // 2)

    total_advance = advances_qs.aggregate(t=Sum('amount'))['t'] or 0
    pending_advance = advances_qs.filter(approved=False).aggregate(t=Sum('amount'))['t'] or 0

    net = earned - total_advance

    # attendance marked-dates set, for calendar-style rendering
    attendance_by_day = {a.date.day: a.day_type for a in attendance_qs}

    first_weekday, days_in_month = calendar.monthrange(year, month)
    # monthrange: Mon=0 ... Sun=6 → convert to Sun=0 ... Sat=6
    sunday_start_offset = (first_weekday + 1) % 7

    calendar_days = []
    for _ in range(sunday_start_offset):
        calendar_days.append(None)  # leading blanks

    for d in range(1, days_in_month + 1):
        day_date = date(year, month, d)
        calendar_days.append({
            'day': d,
            'date': day_date,
            'status': attendance_by_day.get(d),
            'is_future': day_date > today,
            'is_today': day_date == today,
        })

    # prev/next month for nav
    prev_month = month - 1 or 12
    prev_year = year - 1 if month == 1 else year
    next_month = month + 1 if month < 12 else 1
    next_year = year + 1 if month == 12 else year
    is_current_month = (year == today.year and month == today.month)

    context = {
        'employee': employee,
        'today': today,
        'month_label': first_day.strftime('%B %Y'),
        'full_days': full_days,
        'half_days': half_days,
        'earned': earned,
        'total_advance': total_advance,
        'pending_advance': pending_advance,
        'net': net,
        'advances': advances_qs,
        'calendar_days': calendar_days,
        'year': year, 'month': month,
        'prev_year': prev_year, 'prev_month': prev_month,
        'next_year': next_year, 'next_month': next_month,
        'is_current_month': is_current_month,
    }
    return render(request, 'locations/staff_detail.html', context)

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