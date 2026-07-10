from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.views import LoginView
from .forms import LocationForm,PickupForm
from .models import Location,Pickup

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
        # Invalid: fall through and re-render the list with the modal
        # reopened so the person can see what needs fixing.
        show_add_modal = True
    else:
        form = PickupForm()
        show_add_modal = False
 
    pickups = location.pickups.all().order_by("-picked_up_at", "-created_at")
 
    return render(request, "locations/pickup_list.html", {
        "location": location,
        "pickups": pickups,
        "form": form,
        "show_add_modal": show_add_modal,
    })


@login_required
def pickup_detail(request, pk):
    pickup = get_object_or_404(Pickup, pk=pk)
 
    if request.method == "POST":
        if request.POST.get("_method") == "delete":
            location_pk = pickup.location.pk
            pickup.delete()
            messages.success(request, "Pickup deleted.")
            return redirect("location_pickups", pk=location_pk)
 
        # Otherwise: submission from the edit modal
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
    })


@login_required
def all_pickups(request):
    pickups = Pickup.objects.select_related("location").all().order_by("-picked_up_at", "-created_at")
    return render(request, "locations/all_pickups.html", {"pickups": pickups})

@login_required
def quick_add_pickup(request, pk):
    location = get_object_or_404(Location, pk=pk)
    pickup = Pickup.objects.create(location=location)
    messages.success(request, "Pickup created.")
    return redirect("pickup_detail", pk=pickup.pk)

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