from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.views import LoginView
from .forms import LocationForm,OrderForm
from .models import Location,Order

from django.contrib.auth.decorators import login_required

@login_required
def home(request):
    locations = Location.objects.filter(is_active=True).order_by("-updated_at")
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
    locations = (
        Location.objects.filter(is_active=True)
        .exclude(latitude__isnull=True)
        .exclude(longitude__isnull=True)
    )
    return render(request, "locations/location_map.html", {"locations": locations})

@login_required
def location_orders(request, pk):
    location = get_object_or_404(Location, pk=pk)
 
    if request.method == "POST":
        form = OrderForm(request.POST, request.FILES)
        if form.is_valid():
            order = form.save(commit=False)
            order.location = location
            order.save()
            messages.success(request, "Order added.")
            return redirect("location_orders", pk=location.pk)
        # Invalid: fall through and re-render the list with the modal
        # reopened so the person can see what needs fixing.
        show_add_modal = True
    else:
        form = OrderForm()
        show_add_modal = False
 
    orders = location.orders.all().order_by("-date", "-created_at")
 
    return render(request, "locations/order_list.html", {
        "location": location,
        "orders": orders,
        "form": form,
        "show_add_modal": show_add_modal,
    })
    
    
@login_required
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