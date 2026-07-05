from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages

from .forms import LocationForm
from .models import Location


def home(request):
    locations = Location.objects.filter(is_active=True).order_by("-updated_at")
    return render(request, "locations/location_list.html", {"locations": locations})


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


def location_detail(request, pk):
    location = get_object_or_404(Location, pk=pk)

    if request.method == "POST" and request.POST.get("_method") == "delete":
        location.is_active = False # location.delete()
        location.save()
        messages.success(request, f'"{location.name}" was deactivated.')
        return redirect("location_list")

    return render(request, "locations/view_location.html", {"location": location})


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


def location_map(request):
    locations = (
        Location.objects.filter(is_active=True)
        .exclude(latitude__isnull=True)
        .exclude(longitude__isnull=True)
    )
    return render(request, "locations/location_map.html", {"locations": locations})
