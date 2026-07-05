from django import forms
from .models import Location


class LocationForm(forms.ModelForm):
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
            "latitude": forms.TextInput(attrs={
                "class": "field__input",
                "placeholder": "9.9312328",
                "inputmode": "decimal",
                "id": "id_latitude",
            }),
            "longitude": forms.TextInput(attrs={
                "class": "field__input",
                "placeholder": "76.2673041",
                "inputmode": "decimal",
                "id": "id_longitude",
            }),
            "photo": forms.ClearableFileInput(attrs={
                "class": "field__file",
                "accept": "image/*",
                "capture": "environment",
            }),
        }