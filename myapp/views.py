import re
import calendar
from itertools import groupby
from simple_history.utils import get_history_model_for_model
from datetime import date,time
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.db.models import Sum, F, Count, Max
from django.urls import reverse
from django.http import Http404,JsonResponse, HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML

from .forms import LocationForm,PickupForm,ExpenseForm
from .models import Location, Pickup, PickupItem, Item, Employee, Attendance, Advance, Expense
from .utils import get_project_activity, TRACKED_MODELS,staff_required, _date_group_label, _send_telegram, _telegram_enabled, _avatar_color
from .utils import get_tracked_model_by_name, get_display_label
User = get_user_model()

def custom_logout(request):
    from django.contrib.auth import logout
    logout(request)
    return redirect("login")

class LocationsLoginView(LoginView):
    template_name = "locations/login.html"
    redirect_authenticated_user = True
    
@login_required
def project_activity_history(request):
    model_filter = request.GET.get('model') or None
    user_filter = request.GET.get('user') or None
    action_filter = request.GET.get('action') or None
    search = request.GET.get('q') or None

    entries = get_project_activity(
        model_filter=model_filter,
        user_filter=user_filter,
        action_filter=action_filter,
        search=search,
    )

    paginator = Paginator(entries, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'model_choices': [m.__name__ for m in TRACKED_MODELS],
        'user_choices': User.objects.all(),
        'action_choices': [('+', 'Created'), ('~', 'Updated'), ('-', 'Deleted')],
        'current_model': model_filter,
        'current_user': user_filter,
        'current_action': action_filter,
        'current_search': search or '',
    }
    return render(request, 'locations/project_activity_history.html', context)

@login_required
def activity_entry_detail(request, model_name, history_id):
    model = get_tracked_model_by_name(model_name)
    if model is None:
        raise Http404("Unknown model")

    history_model = get_history_model_for_model(model)
    record = get_object_or_404(history_model, pk=history_id)

    # Find the previous historical record for the same object to build a diff
    previous_record = (
        history_model.objects
        .filter(id=record.id, history_date__lt=record.history_date)
        .order_by('-history_date')
        .first()
    )

    changes = []
    if previous_record:
        delta = record.diff_against(previous_record)
        for change in delta.changes:
            changes.append({
                'field': change.field,
                'old': change.old,
                'new': change.new,
            })
    elif record.history_type == '+':
        # Creation record — show initial field values instead of a diff
        for field in model._meta.fields:
            if field.name in ('id',):
                continue
            changes.append({
                'field': field.name,
                'old': None,
                'new': getattr(record, field.name, None),
            })

    # Full timeline for this specific object (all versions), most recent first
    object_history = history_model.objects.filter(id=record.id).order_by('-history_date')

    context = {
        'model_name': model_name,
        'record': record,
        'label': get_display_label(record, model),
        'changes': changes,
        'object_history': object_history,
        'action_label': {'+': 'Created', '~': 'Updated', '-': 'Deleted'}.get(record.history_type),
    }
    return render(request, 'locations/activity_entry_detail.html', context)



@login_required
def change_password(request):
    if request.method == "POST":
        new_password = request.POST.get("new_password", "")
        request.user.set_password(new_password)
        request.user.save()
        update_session_auth_hash(request, request.user)  # keeps the user logged in
        messages.success(request, "Password updated.")
    return redirect('list_staff')

@login_required
def list_location(request):
    if not request.user.is_staff:
        return redirect('list_staff')
    locations = Location.objects.filter(is_active=True).order_by("name")
    return render(request, "locations/list_location.html", {"locations": locations})

@staff_required
def location_create(request):
    if request.method == "POST":
        form = LocationForm(request.POST, request.FILES)
        if form.is_valid():
            location = form.save()
            messages.success(request, f'"{location.name}" was added.')
            return redirect("list_location")
    else:
        form = LocationForm()
    return render(request, "locations/add_location.html", {"form": form})

@staff_required
def location_detail(request, pk):
    location = get_object_or_404(Location, pk=pk)

    if request.method == "POST" and request.POST.get("_method") == "delete":
        location.is_active = False # location.delete()
        location.save()
        messages.success(request, f'"{location.name}" was deactivated.')
        return redirect("list_location")
    pickups = location.pickups.exclude(status=Pickup.STATUS_CANCELLED).order_by("-created_at")
    return render(request, "locations/view_location.html", {"location": location,"pickups": pickups})

@staff_required
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

@staff_required
def update_location_balance(request, pk):
    location = get_object_or_404(Location, pk=pk)
    if request.method == "POST":
        raw_balance = request.POST.get("balance", "").strip()
        if raw_balance == "":
            location.balance = None
        else:
            try:
                location.balance = int(raw_balance)
            except ValueError:
                messages.error(request, "Enter a valid whole number.")
                return redirect("location_detail", pk=location.pk)
        location.save(update_fields=["balance"])
        messages.success(request, "Balance updated.")
    return redirect("location_detail", pk=location.pk)

@staff_required
def location_map(request):
    locations = Location.objects.filter(is_active=True).exclude(latitude__isnull=True).exclude(longitude__isnull=True)
    return render(request, "locations/location_map.html", {"locations": locations})



@staff_required
def list_pickup(request):
    tab = request.GET.get("tab", "pending")
    if tab not in ("pending", "picked_up"):
        tab = "pending"

    pickups = Pickup.objects.select_related("location").filter(
        status=tab
    ).order_by("-created_at")

    today = timezone.localdate()

    def group_date(p):
        return timezone.localtime(p.created_at).date()

    grouped_pickups = [
        {"label": _date_group_label(d, today), "days_ago": (today - d).days, "pickups": list(items)}
        for d, items in groupby(pickups, key=group_date)
    ]

    return render(request, "locations/list_pickup.html", {
        "pickups": pickups,
        "current_tab": tab,
        "grouped_pickups": grouped_pickups,
    })
    
@staff_required
def view_pickup(request, pk):
    pickup = get_object_or_404(Pickup, pk=pk)

    if request.method == "POST":
        if request.POST.get("_method") == "delete":
            location_pk = pickup.location.pk
            pickup.status=Pickup.STATUS_CANCELLED
            pickup.save()
            messages.success(request, "Pickup cancelled.")
            return redirect("list_pickup")

        form = PickupForm(request.POST, request.FILES, instance=pickup)
        if form.is_valid():
            form.save()
            messages.success(request, "Pickup updated.")
            return redirect("view_pickup", pk=pickup.pk)
        show_edit_modal = True
    else:
        form = PickupForm(instance=pickup)
        show_edit_modal = False

    pickup_items = pickup.items.select_related("item").all()
    total_qty = pickup_items.aggregate(total=Sum("quantity"))["total"] or 0
    return render(request, "locations/view_pickup.html", {
        "pickup": pickup,
        "location": pickup.location,
        "form": form,
        "show_edit_modal": show_edit_modal,
        "dry_items": Item.objects.filter(item_category=Item.CATEGORY_DRYCLEANING),
        "iron_items": Item.objects.filter(item_category=Item.CATEGORY_IRONING),
        "pickup_items": pickup_items,
        "total_qty": total_qty,
    })
    
@staff_required
def list_order(request):
    only_finished = request.GET.get("only_finished") == "on"

    pickups_qs = Pickup.objects.select_related("location").annotate(
        total_items=Sum("items__quantity")
    )

    if only_finished:
        pickups_qs = pickups_qs.filter(status=Pickup.STATUS_FINISHED)
    else:
        pickups_qs = pickups_qs.filter(
            status__in=[Pickup.STATUS_FINISHED, Pickup.STATUS_DELIVERED]
        )

    pickups_qs = pickups_qs.order_by("-invoice_id", "-created_at")

    paginator = Paginator(pickups_qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "locations/list_order.html", {
        "page_obj": page_obj,
        "only_finished": only_finished,
    })
    
@staff_required
def add_pickup_items_page(request, pk):
    pickup = get_object_or_404(Pickup, pk=pk)
    category = request.GET.get("category", "i")
    if category not in ("d", "i"):
        category = "i"
    context = {
        "pickup": pickup,
        "category": category,
        "dry_items": Item.objects.filter(item_category="d"),
        "iron_items": Item.objects.filter(item_category="i"),
    }
    return render(request, "locations/add_pickup_items.html", context)


@staff_required
def add_pickup_items(request, pk):
    pickup = get_object_or_404(Pickup, pk=pk)
    item_names = request.POST.getlist("item_name")
    quantities = request.POST.getlist("quantity")
    prices = request.POST.getlist("price")
    category = request.POST.get("item_category")
    if category not in (Item.CATEGORY_DRYCLEANING, Item.CATEGORY_IRONING):
        category = Item.CATEGORY_DRYCLEANING

    created = 0
    updated = 0
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

        pickup_item, was_created = PickupItem.objects.get_or_create(
            pickup=pickup, item=item,
            defaults={"quantity": quantity, "price": price},
        )
        if was_created:
            created += 1
        else:
            # Item's already on this pickup — merge quantities instead of
            # erroring, and refresh the price to whatever was entered/looked up.
            pickup_item.quantity = F("quantity") + quantity
            pickup_item.price = price
            pickup_item.save(update_fields=["quantity", "price"])
            updated += 1

    if created or updated:
        if pickup.invoice_id is None:
            last_invoice = Pickup.objects.aggregate(m=Max("invoice_id"))["m"] or 0
            pickup.invoice_id = last_invoice + 1
            pickup.save(update_fields=["invoice_id"])
            
        if pickup.status != Pickup.STATUS_FINISHED:
            pickup.status = Pickup.STATUS_FINISHED
            pickup.save(update_fields=["status"])
        parts = []
        if created:
            parts.append(f"added {created} item{'s' if created != 1 else ''}")
        if updated:
            parts.append(f"updated {updated} existing item{'s' if updated != 1 else ''}")
        messages.success(request, " and ".join(parts).capitalize() + ".")
    else:
        messages.error(request, "No items were entered.")
        return redirect(f"{reverse('add_pickup_items_page', args=[pickup.pk])}?category={category}")

    return redirect("view_pickup", pk=pickup.pk)
 
@staff_required
def pickup_invoice(request, pk):
    pickup = get_object_or_404(Pickup, pk=pk)
    pickup_items = pickup.items.select_related("item").all()

    html_string = render_to_string("locations/invoice.html", {
        "pickup": pickup,
        "location": pickup.location,
        "pickup_items": pickup_items,
    })

    pdf = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    filename = f"invoice_{pickup.invoice_id}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

@staff_required
def remove_pickup_item(request, pk):
    pickup_item = get_object_or_404(PickupItem, pk=pk)
    pickup_pk = pickup_item.pickup.pk
    pickup_item.delete()
    messages.success(request, "Item removed.")
    return redirect("view_pickup", pk=pickup_pk)

@staff_required
def create_item(request):
    pickup_pk = request.POST["pickup_pk"] # used to redirect back to the pickup detail page
    name = re.sub(r"\s+","_",request.POST["name"].strip().lower())
    category = request.POST["item_category"]
    if Item.objects.filter( name=name, item_category=category).exists():
        messages.error(request, "Item already exists.")
        return redirect("view_pickup", pk=pickup_pk)
    Item.objects.create(name=name,item_category=category,price=int(request.POST["price"]))
    messages.success(request, "Item created.")
    return redirect("view_pickup", pk=pickup_pk)

@staff_required
def update_item_price(request, pk):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"}, status=405)

    item = get_object_or_404(Item, pk=pk)
    raw_price = (request.POST.get("price") or "").strip()
    try:
        price = int(raw_price)
        if price < 0:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Invalid price"}, status=400)

    item.price = price
    item.save(update_fields=["price"])
    return JsonResponse({"ok": True, "price": item.price})

@staff_required
def mark_pickup_paid(request, pk):
    pickup = get_object_or_404(Pickup, pk=pk)
    if request.method == "POST":
        method = request.POST.get("payment_method")
        amount = request.POST.get("amount") or ""
        try:
            amount = int(float(amount)) if amount.strip() else None
        except (TypeError, ValueError):
            amount = None
        if method in (Pickup.PAYMENT_UPI, Pickup.PAYMENT_CASH) and amount is not None:
            pickup.payment_method = method
            pickup.amount_paid = amount
            pickup.paid_at = timezone.now()
            if pickup.status != Pickup.STATUS_DELIVERED:
                pickup.status = Pickup.STATUS_DELIVERED
                pickup.delivered_at = timezone.now()
                messages.success(request, f"Marked paid via {pickup.get_payment_method_display()} and delivered.")
            else:
                messages.success(request, f"Marked paid via {pickup.get_payment_method_display()}.")
            pickup.save()
            if _telegram_enabled('mark_pickup_paid'):
                _send_telegram(
                    f"💰 *Payment Received*\n"
                    f"📍 {pickup.location.name}\n"
                    f"💳 {pickup.get_payment_method_display()}: ₹{pickup.amount_paid}\n"
                    f"🕐 {timezone.localtime(pickup.paid_at).strftime('%b %d, %Y · %I:%M %p')}"
                )
        else:
            messages.error(request, "Select a payment method and enter a valid amount.")
    return redirect("view_pickup", pk=pickup.pk)

   
@staff_required
def quick_add_pickup(request, pk):
    location = get_object_or_404(Location, pk=pk)
    pickup = Pickup.objects.create(location=location)
    if _telegram_enabled('quick_add_pickup'):
        text = (
            f"📦 *New Pickup Created*\n"
            f"📍 *Location:* {location.name}\n"
            f"🏠 {location.house_name or '—'}\n"
            f"🕐 {timezone.localtime(pickup.created_at).strftime('%b %d, %Y · %I:%M %p')}\n\n"
            f"[View on GoogleMap](https://www.google.com/maps?q={location.latitude},{location.longitude})"
        )
        _send_telegram(text)
    messages.success(request, "Pickup created.")
    return redirect("list_pickup")

@staff_required
def set_pickup_status(request, pk, status):
    if status not in (Pickup.STATUS_PICKED_UP, Pickup.STATUS_FINISHED, Pickup.STATUS_DELIVERED):
        return redirect(request.META.get("HTTP_REFERER", "list_pickup"))
 
    pickup = get_object_or_404(Pickup, pk=pk)
    pickup.status = status
 
    now = timezone.now()
    if status == Pickup.STATUS_PICKED_UP and not pickup.picked_up_at:
        pickup.picked_up_at = now
    elif status == Pickup.STATUS_DELIVERED and not pickup.delivered_at:
        pickup.delivered_at = now
 
    pickup.save()
    if _telegram_enabled('set_pickup_status'):
        _send_telegram(
            f"🔄 *Status Updated*\n"
            f"📍 {pickup.location.name}\n"
            f"➡️ {pickup.get_status_display()}\n"
            f"🕐 {timezone.localtime(now).strftime('%b %d, %Y · %I:%M %p')}"
        )
    messages.success(request, f"Marked as {pickup.get_status_display()}.")
    return redirect(request.META.get("HTTP_REFERER", "list_pickup"))


@staff_required
def list_expense(request):
    today = timezone.localdate()
    expenses_qs = Expense.objects.select_related("added_by").filter(date=today)

    paginator = Paginator(expenses_qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    today_total = expenses_qs.aggregate(t=Sum("amount"))["t"] or 0

    def group_date(e):
        return e.date

    grouped_expenses = [
        {"label": _date_group_label(d, today), "expenses": list(items)}
        for d, items in groupby(page_obj.object_list, key=group_date)
    ]

    return render(request, "locations/list_expense.html", {
        "page_obj": page_obj,
        "grouped_expenses": grouped_expenses,
        "today_total": today_total,
        "today": today,
    })


@staff_required
def add_expense(request):
    if request.method == "POST":
        form = ExpenseForm(request.POST)
        if form.is_valid():
            entries = form.save_all(added_by=request.user)
            if len(entries) > 1:
                total = sum(e.amount for e in entries)
                messages.success(
                    request,
                    f"Split into {len(entries)} daily entries (₹{total} total)."
                )
            else:
                messages.success(request, "Expense added.")
            return redirect("daily_dashboard")
    else:
        form = ExpenseForm(initial={"date": timezone.localdate()})
    return render(request, "locations/add_expense.html", {"form": form})


@staff_required
def delete_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == "POST":
        expense.delete()
        messages.success(request, "Expense removed.")
    return redirect("list_expense")


@staff_required
def daily_dashboard(request):
    today = timezone.localdate()
    date_str = request.GET.get("date")
    try:
        day = date.fromisoformat(date_str) if date_str else today
    except ValueError:
        day = today
 
    # --- Payments received (money actually collected today) ---
    paid_today = Pickup.objects.filter(paid_at__date=day).select_related("location").order_by("-paid_at")
    upi_total = 0
    cash_total = 0
    for p in paid_today:
        if p.payment_method == Pickup.PAYMENT_UPI:
            upi_total += p.amount_paid or 0
        elif p.payment_method == Pickup.PAYMENT_CASH:
            cash_total += p.amount_paid or 0
    total_received = upi_total + cash_total
 
    # --- Sales: value of items added to pickups today ---
    total_sales = PickupItem.objects.filter(created_at__date=day).aggregate(
        t=Sum(F("price") * F("quantity"))
    )["t"] or 0
 
    # --- Expenses: wages earned today, advances given today, other expenses today ---
    todays_attendance = Attendance.objects.filter(date=day).select_related("employee__user").order_by("employee__user__first_name")
    wage_rows = []
    wage_total = 0
    for a in todays_attendance:
        wage = a.employee.daily_wage if a.day_type == "full" else a.employee.daily_wage // 2
        wage_total += wage
        wage_rows.append({
            "name": a.employee.user.get_full_name() or a.employee.user.username,
            "day_type": a.day_type,
            "wage": wage,
        })
 
    advances_today = Advance.objects.filter(date=day).select_related("employee__user").order_by("-id")
    advance_total = advances_today.aggregate(t=Sum("amount"))["t"] or 0
 
    expenses_today = Expense.objects.filter(date=day).order_by("-id")
    other_expense_total = expenses_today.aggregate(t=Sum("amount"))["t"] or 0
 
    total_expense = wage_total + advance_total + other_expense_total
 
    profit = total_received - total_expense
 
    prev_day = day - timezone.timedelta(days=1)
    next_day = day + timezone.timedelta(days=1)
 
    context = {
        "day": day,
        "today": today,
        "is_today": day == today,
        "prev_day": prev_day,
        "next_day": next_day,
        "upi_total": upi_total,
        "cash_total": cash_total,
        "total_received": total_received,
        "total_sales": total_sales,
        "wage_total": wage_total,
        "advance_total": advance_total,
        "other_expense_total": other_expense_total,
        "total_expense": total_expense,
        "profit": profit,
        "paid_pickups": paid_today,
        "wage_rows": wage_rows,
        "advances_today": advances_today,
        "expenses_today": expenses_today,
    }
    return render(request, "locations/daily_dashboard.html", context)


@login_required
def list_staff(request):
    today = timezone.localdate()
    employees = Employee.objects.filter(is_active=True).order_by('user__first_name')

    todays_attendance = {
        a.employee_id: a
        for a in Attendance.objects.filter(employee__in=employees, date=today)
    }

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

    staff_today = []
    for emp in employees:
        att = todays_attendance.get(emp.id)
        full_days = full_counts.get(emp.id, 0)
        half_days = half_counts.get(emp.id, 0)
        advance = advance_totals.get(emp.id, 0)
        earned = round(emp.daily_wage * (full_days + 0.5 * half_days))
        staff_today.append({
            'id': emp.id,
            'name': emp.user.get_full_name() or emp.user.username,
            'color': _avatar_color(emp.id),
            'marked_time': timezone.localtime(att.marked_at).strftime('%-I:%M %p') if att else None,
            'status': att.day_type if att else 'pending',
            'net': earned - advance,
        })

    return render(request, 'locations/list_staff.html', {
        'staff_today': staff_today,
        'today': today,
    })
 
@login_required
def mark_attendance(request):
    if not (time(8, 0) <= timezone.localtime().time() <= time(20, 0)):
        messages.error(request, 'You can only mark attendance between 8:00 AM and 8:00 PM.')
        return redirect('list_staff')
    employee = request.user.employee
    day_type = request.GET.get('day_type', 'full')
    if day_type not in ('full', 'half'):
        day_type = 'full'
    obj, created = Attendance.objects.get_or_create(
        employee=employee,
        date=timezone.localdate(),
        defaults={'day_type': day_type}
    )
    if not created:
        messages.error(request, 'Already marked for today')
        return redirect('list_staff')
    label = 'Full day' if day_type == 'full' else 'Half day'
    messages.success(request, f'Marked {employee.user.first_name} as {label}.')
    return redirect('list_staff')

@login_required
def add_advance(request):
    if request.method == "POST":
        employee = request.user.employee
        amount = request.POST.get("amount", "").strip()
        note = request.POST.get("note", "").strip()
        Advance.objects.create(employee=employee, amount=amount, note=note)
        return redirect('list_staff')
    return render(request, "locations/add_advance.html")



@login_required
def view_staff(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if not request.user.is_staff and employee.user_id != request.user.id:
        raise PermissionDenied
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
    return render(request, 'locations/view_staff.html', context)


def _back_to_month(pk, year, month):
    return redirect(f"{reverse('view_staff', args=[pk])}?year={year}&month={month}")
 
 
@login_required
def toggle_attendance(request, pk, year, month, day):
    """Cycle a single day's attendance: none -> full -> half -> none."""
    if not request.user.is_staff:
        raise PermissionDenied
 
    employee = get_object_or_404(Employee, pk=pk)
 
    try:
        day_date = date(int(year), int(month), int(day))
    except ValueError:
        raise PermissionDenied
 
    if day_date > timezone.localdate():
        # Can't mark attendance for a day that hasn't happened yet.
        return _back_to_month(pk, year, month)
 
    attendance = Attendance.objects.filter(employee=employee, date=day_date).first()
 
    if attendance is None:
        Attendance.objects.create(employee=employee, date=day_date, day_type='full')
    elif attendance.day_type == 'full':
        attendance.day_type = 'half'
        attendance.save(update_fields=['day_type'])
    else:  # half -> clear
        attendance.delete()
 
    return _back_to_month(pk, year, month)
 
 
@login_required
def update_wage(request, pk):
    """Edit an employee's per-day wage."""
    if not request.user.is_staff:
        raise PermissionDenied
 
    employee = get_object_or_404(Employee, pk=pk)
    year = request.POST.get('year') or timezone.localdate().year
    month = request.POST.get('month') or timezone.localdate().month
 
    raw_wage = request.POST.get('daily_wage', '').strip()
 
    employee.daily_wage = raw_wage
    employee.save(update_fields=['daily_wage'])
    messages.success(request, "Daily wage updated.")
    return _back_to_month(pk, year, month)
 
 
@login_required
def delete_advance(request, pk, advance_pk):
    """Remove an advance entry."""
    if not request.user.is_staff:
        raise PermissionDenied
 
    advance = get_object_or_404(Advance, pk=advance_pk, employee_id=pk)
    year, month = advance.date.year, advance.date.month
    advance.delete()
    messages.success(request, "Advance removed.")
    return _back_to_month(pk, year, month)


@staff_required
def dashboard(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except ValueError:
        year, month = today.year, today.month

    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    # --- Pickups ---
    pickups_qs = Pickup.objects.filter(
        created_at__date__range=(first_day, last_day)
    ).exclude(status=Pickup.STATUS_CANCELLED)
    total_pickups = pickups_qs.count()
    status_counts = {
        row['status']: row['count']
        for row in pickups_qs.values('status').annotate(count=Count('id'))
    }

    pickups_by_location = list(
        pickups_qs.values('location__name')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    # --- Sales ---
    paid_pickups = Pickup.objects.filter(paid_at__date__range=(first_day, last_day))
    total_sales = paid_pickups.aggregate(t=Sum('amount_paid'))['t'] or 0
    sales_by_method = {
        row['payment_method']: row['t']
        for row in paid_pickups.values('payment_method').annotate(t=Sum('amount_paid'))
    }
    sales_by_location = list(
        paid_pickups.values('location__name')
        .annotate(total=Sum('amount_paid'))
        .order_by('-total')[:10]
    )

    # --- Attendance / wage cost ---
    employees = Employee.objects.filter(is_active=True)
    attendance_qs = Attendance.objects.filter(date__range=(first_day, last_day))

    attendance_by_employee = []
    total_expense = 0
    for emp in employees:
        full = attendance_qs.filter(employee=emp, day_type='full').count()
        half = attendance_qs.filter(employee=emp, day_type='half').count()
        cost = round(emp.daily_wage * (full + 0.5 * half))
        total_expense += cost
        if full or half:
            attendance_by_employee.append({
                'name': emp.user.get_full_name() or emp.user.username,
                'full': full, 'half': half, 'cost': cost,
            })

    total_advances = Advance.objects.filter(
        date__range=(first_day, last_day)
    ).aggregate(t=Sum('amount'))['t'] or 0

    profit = total_sales - total_expense

    # --- New locations ---
    new_locations = Location.objects.filter(
        created_at__date__range=(first_day, last_day)
    ).count()

    # prev/next month nav
    prev_month = month - 1 or 12
    prev_year = year - 1 if month == 1 else year
    next_month = month + 1 if month < 12 else 1
    next_year = year + 1 if month == 12 else year
    is_current_month = (year == today.year and month == today.month)

    context = {
        'month_label': first_day.strftime('%B %Y'),
        'year': year, 'month': month,
        'prev_year': prev_year, 'prev_month': prev_month,
        'next_year': next_year, 'next_month': next_month,
        'is_current_month': is_current_month,

        'total_pickups': total_pickups,
        'status_counts': status_counts,
        'pickups_by_location': pickups_by_location,

        'total_sales': total_sales,
        'sales_by_method': sales_by_method,
        'sales_by_location': sales_by_location,
        'total_expense': total_expense,
        'total_advances': total_advances,
        'profit': profit,

        'attendance_by_employee': attendance_by_employee,
        'new_locations': new_locations,
    }
    return render(request, 'locations/dashboard.html', context)

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
