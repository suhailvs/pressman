from django.shortcuts import get_object_or_404, redirect, render
import requests
from django.contrib import messages

from .forms import LocationForm
from .models import Location


def get_lat_lon(final_url):
    import re
    from urllib.parse import urlparse, parse_qs

    m = re.search(r"(-?\d+\.\d+),(-?\d+\.\d+)", final_url)
    if m:
        return float(m.group(1)), float(m.group(2))
    params = parse_qs(urlparse(final_url).query)
    for key in ("q", "query"):
        if key in params:
            lat, lon = map(float, params[key][0].split(","))
            return lat, lon
    return None


def home(request):
    # response = requests.get("https://maps.app.goo.gl/j5WbXh99bk4pha7A6?g_st=aw", allow_redirects=True)
    # print(get_lat_lon((response.url)))
    locations = Location.objects.all().order_by("-updated_at")
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
        name = location.name
        location.delete()
        messages.success(request, f'"{name}" was deleted.')
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
