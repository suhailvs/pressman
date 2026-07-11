import re
import requests
from decimal import Decimal, ROUND_HALF_UP
from django import forms
from .models import Location,Pickup


class LocationForm(forms.ModelForm):
    maps_url = forms.CharField(
        label="Google Maps link",
        required=False,  # optional now — required only enforced in clean() for create
        widget=forms.TextInput(attrs={
            "class": "field__input",
            "placeholder": "Paste a Google Maps link here",
            "id": "id_maps_url",
            "autocomplete": "off",
        }),
    )

    class Meta:
        model = Location
        fields = ["name", "house_name", "phone", "latitude", "longitude", "photo"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "field__input",
                "placeholder": "e.g. Green Valley Apartments",
                "autofocus": True,
            }),
            "house_name": forms.TextInput(attrs={
                "class": "field__input",
                "placeholder": "e.g. House No. 24, 2nd Floor",
            }),
            "phone": forms.TextInput(attrs={
                "class": "field__input",
                "placeholder": "e.g. +91 98765 43210",
                "type": "tel",
            }),
            "latitude": forms.HiddenInput(attrs={"id": "id_latitude"}),
            "longitude": forms.HiddenInput(attrs={"id": "id_longitude"}),
            "photo": forms.ClearableFileInput(attrs={
                "class": "field__file",
                "accept": "image/*",
                "capture": "environment",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["latitude"].required = False
        self.fields["longitude"].required = False

        # On the edit form, pre-fill maps_url with a link built from the
        # existing coordinates, so the field isn't blank when opening it.
        if self.instance and self.instance.pk and self.instance.latitude and self.instance.longitude:
            self.fields["maps_url"].initial = (
                f"https://www.google.com/maps/@"
                f"{self.instance.latitude},{self.instance.longitude},17z"
            )

    COORD_PATTERNS = [
        r"!3d(-?\d{1,3}\.\d+)!4d(-?\d{1,3}\.\d+)",
        r"/place/(-?\d{1,3}\.\d+),\s*(-?\d{1,3}\.\d+)",
        r"[@](-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)",
        r"[?&]q=(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)",
        r"(-?\d{1,3}\.\d{3,}),\s*(-?\d{1,3}\.\d{3,})",
    ]

    @classmethod
    def extract_coordinates(cls, url):
        """Return (lat, lng) as Decimal, rounded to 7 places, or (None, None)."""
        url = url.strip()

        if "goo.gl" in url:
            try:
                resp = requests.head(url, allow_redirects=True, timeout=5)
                url = resp.url
            except requests.RequestException:
                try:
                    resp = requests.get(url, allow_redirects=True, timeout=5)
                    url = resp.url
                except requests.RequestException:
                    pass

        for pattern in cls.COORD_PATTERNS:
            match = re.search(pattern, url)
            if match:
                try:
                    lat = Decimal(match.group(1)).quantize(
                        Decimal("0.0000001"), rounding=ROUND_HALF_UP
                    )
                    lng = Decimal(match.group(2)).quantize(
                        Decimal("0.0000001"), rounding=ROUND_HALF_UP
                    )
                except Exception:
                    continue
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    return lat, lng
        return None, None

    def clean(self):
        cleaned_data = super().clean()
        maps_url = (cleaned_data.get("maps_url") or "").strip()

        if maps_url:
            lat, lng = self.extract_coordinates(maps_url)
            if lat is None or lng is None:
                self.add_error(
                    "maps_url",
                    "Couldn't find coordinates in that link. Open the pin in "
                    "Google Maps, tap Share, and paste the full link here.",
                )
            else:
                cleaned_data["latitude"] = lat
                cleaned_data["longitude"] = lng
        elif not self.instance.pk:
            # Creating a new location with no link at all
            self.add_error("maps_url", "Please paste a Google Maps link.")
        # else: editing and left blank -> keep the instance's existing lat/lng untouched

        return cleaned_data

class PickupForm(forms.ModelForm):
    picked_up_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(attrs={
            "class": "field__input",
            "type": "datetime-local",
        }, format="%Y-%m-%dT%H:%M"),
    )
    delivered_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(attrs={
            "class": "field__input",
            "type": "datetime-local",
        }, format="%Y-%m-%dT%H:%M"),
    )
    class Meta:
        model = Pickup
        fields = ["status", "picked_up_at", "delivered_at", "note", "photo"]
        widgets = {
            "status": forms.Select(attrs={
                "class": "field__input",
            }),
            "note": forms.Textarea(attrs={
                "class": "field__input field__input--textarea",
                "placeholder": "What was ordered, quantity, anything worth noting…",
                "rows": 3,
            }),
            "photo": forms.ClearableFileInput(attrs={
                "class": "field__file",
                "accept": "image/*",
                "capture": "environment",
            }),
        }
 