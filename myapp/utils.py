import requests
from functools import wraps

from simple_history.utils import get_history_model_for_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import (
    GeneralSettings, User, Location, Pickup, Item,
    PickupItem, Employee, Advance, Attendance,
)

# Models we want to include in the unified activity feed
TRACKED_MODELS = [
    GeneralSettings, User, Location, Pickup,
    Item, PickupItem, Employee, Advance, Attendance,
]

ACTION_LABELS = {'+': 'Created', '~': 'Updated', '-': 'Deleted'}

TELEGRAM_BOT_TOKEN = "8574559583:AAG7tRjCSCbW4DkQx3P4a3X44Wp9Ba7RKB4"
TELEGRAM_CHAT_ID = -5579934168
# Cycled avatar colors so each employee gets a stable-ish color by id.
AVATAR_COLORS = ['#128C7E', '#3A7CA5', '#C0533A', '#6B4FA8', '#B8860B', '#4C7A3D']


def get_tracked_model_by_name(name):
    for model in TRACKED_MODELS:
        if model.__name__ == name:
            return model
    return None

def _avatar_color(employee_id):
    return AVATAR_COLORS[employee_id % len(AVATAR_COLORS)]

def _telegram_enabled(key):
    return GeneralSettings.objects.filter(key=key, value='t').exists()

def _send_telegram(text):
    if not _telegram_enabled("telegram_enabled"):
        return
    # telegram bot see: https://github.com/suhailvs-archive/stack/blob/main/backend/api/views.py
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={'chat_id': TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True},
            timeout=5,
        )
    except requests.RequestException:
        pass

def staff_required(view_func):
    """Like @login_required, but also requires request.user.is_staff."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


def _date_group_label(d, today):
    delta = (today - d).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    if 2 <= delta <= 6:
        return d.strftime("%A")  # e.g. "Sunday"
    return d.strftime("%b %d, %Y")  # e.g. "Jul 28, 2026"

def get_display_label(instance_record, model):
    """Best-effort human readable label for a historical row."""
    if model is Location:
        return instance_record.name
    if model is Pickup:
        return f"Pickup #{instance_record.id} ({instance_record.status})"
    if model is Item:
        return instance_record.name
    if model is PickupItem:
        return f"PickupItem #{instance_record.id}"
    if model is Employee:
        return f"Employee #{instance_record.id}"
    if model is Advance:
        return f"Advance #{instance_record.id}"
    if model is Attendance:
        return f"Attendance #{instance_record.id}"
    if model is User:
        return instance_record.username
    if model is GeneralSettings:
        return instance_record.key
    return str(instance_record.pk)


def get_project_activity(limit=None, model_filter=None, user_filter=None,
                          action_filter=None, search=None):
    """
    Returns a list of dicts representing historical changes across
    every tracked model, merged and sorted by history_date descending.
    """
    entries = []
    models_to_query = TRACKED_MODELS

    if model_filter:
        models_to_query = [m for m in TRACKED_MODELS if m.__name__ == model_filter]

    for model in models_to_query:
        history_model = get_history_model_for_model(model)
        qs = history_model.objects.all().select_related('history_user')

        if user_filter:
            qs = qs.filter(history_user_id=user_filter)
        if action_filter:
            qs = qs.filter(history_type=action_filter)

        for record in qs:
            label = get_display_label(record, model)
            if search and search.lower() not in label.lower():
                continue

            entries.append({
                'model_name': model.__name__,
                'object_id': record.pk if hasattr(record, 'pk') else record.id,
                'label': label,
                'action': ACTION_LABELS.get(record.history_type, record.history_type),
                'action_code': record.history_type,
                'date': record.history_date,
                'user': record.history_user,
                'record': record,
            })

    entries.sort(key=lambda e: e['date'], reverse=True)

    if limit:
        entries = entries[:limit]

    return entries