import re
import requests
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from django import forms
from .models import Location,Pickup,Expense


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
                # "capture": "environment",
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
        # elif not self.instance.pk:
        #     # Creating a new location with no link at all
        #     self.add_error("maps_url", "Please paste a Google Maps link.")
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
                # "capture": "environment",
            }),
        }

class ExpenseForm(forms.ModelForm):
    is_periodic = forms.BooleanField(
        required=False,
        label="This covers a period (e.g. rent, electricity bill)",
        widget=forms.CheckboxInput(attrs={"id": "id_is_periodic"}),
    )

    class Meta:
        model = Expense
        fields = ["date", "amount", "category", "note", "period_start", "period_end"]
        widgets = {
            "date": forms.DateInput(attrs={
                "class": "field__input",
                "type": "date",
            }),
            "amount": forms.NumberInput(attrs={
                "class": "field__input",
                "min": "1",
                "step": "1",
                "inputmode": "decimal",
                "placeholder": "0",
            }),
            "category": forms.Select(attrs={
                "class": "field__input",
            }),
            "note": forms.TextInput(attrs={
                "class": "field__input",
                "placeholder": "What was this for? (optional)",
            }),
            "period_start": forms.DateInput(attrs={
                "class": "field__input",
                "type": "date",
                "id": "id_period_start",
            }),
            "period_end": forms.DateInput(attrs={
                "class": "field__input",
                "type": "date",
                "id": "id_period_end",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["period_start"].required = False
        self.fields["period_end"].required = False
        if self.instance and self.instance.pk and self.instance.covers_period:
            self.fields["is_periodic"].initial = True

    def clean(self):
        cleaned_data = super().clean()
        is_periodic = cleaned_data.get("is_periodic")
        period_start = cleaned_data.get("period_start")
        period_end = cleaned_data.get("period_end")

        if is_periodic:
            if not period_start or not period_end:
                self.add_error(
                    "period_start" if not period_start else "period_end",
                    "Enter both a start and end date for the period this covers.",
                )
            elif period_end < period_start:
                self.add_error("period_end", "End date can't be before the start date.")
        else:
            cleaned_data["period_start"] = None
            cleaned_data["period_end"] = None

        return cleaned_data

    def save(self, commit=True):
        """
        Kept for API compatibility — always use save_all() instead, which
        handles the periodic split into multiple daily entries. This just
        saves a single non-periodic entry.
        """
        instance = super().save(commit=False)
        instance.period_start = None
        instance.period_end = None
        if commit:
            instance.save()
        return instance

    def save_all(self, added_by=None):
        """
        Save this form. For a normal (non-periodic) expense this creates one
        Expense row. For a periodic expense (period_start/period_end set),
        this splits the total amount evenly across every day in the range —
        one Expense row per day — so each day carries its own share, with
        any remainder (from amounts that don't divide evenly) added to the
        first few days so the split always sums back to the exact total.

        Returns a list of the saved Expense instances (length 1 for a
        non-periodic expense).
        """
        is_periodic = self.cleaned_data.get("is_periodic")
        category = self.cleaned_data["category"]
        note = self.cleaned_data.get("note", "")
        amount = self.cleaned_data["amount"]

        if not is_periodic:
            instance = super().save(commit=False)
            instance.period_start = None
            instance.period_end = None
            instance.added_by = added_by
            instance.save()
            return [instance]

        period_start = self.cleaned_data["period_start"]
        period_end = self.cleaned_data["period_end"]
        num_days = (period_end - period_start).days + 1

        base_amount, remainder = divmod(amount, num_days)

        entries = []
        for i in range(num_days):
            day = period_start + timedelta(days=i)
            # Give the extra rupees (from the remainder) to the first
            # `remainder` days, so the entries sum to exactly `amount`.
            day_amount = base_amount + (1 if i < remainder else 0)
            entry = Expense.objects.create(
                date=day,
                amount=day_amount,
                category=category,
                note=note,
                period_start=period_start,
                period_end=period_end,
                added_by=added_by,
            )
            entries.append(entry)
        return entries