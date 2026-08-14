"""Test suite for the `myapp` app."""

import tempfile
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import LocationForm, PickupForm
from .models import Item, Location, Pickup, PickupItem

User = get_user_model()

# A genuinely valid 1x1 pixel GIF, so Pillow-backed ImageField validation
# (which actually opens and identifies the file) passes in form tests.
TINY_GIF = (
    b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00"
    b"\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def make_test_photo(name="test.gif"):
    return SimpleUploadedFile(name, TINY_GIF, content_type="image/gif")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class LocationModelTests(TestCase):
    def test_str_and_defaults(self):
        location = Location.objects.create(
            name="Green Valley Apartments",
            latitude=Decimal("9.9312328"),
            longitude=Decimal("76.2673041"),
        )
        self.assertTrue(location.is_active)
        self.assertIsNotNone(location.created_at)
        self.assertIsNotNone(location.updated_at)

    def test_soft_delete_via_is_active(self):
        location = Location.objects.create(
            name="Test Place", latitude=Decimal("1.0"), longitude=Decimal("1.0")
        )
        location.is_active = False
        location.save()
        location.refresh_from_db()
        self.assertFalse(location.is_active)
        # Still exists in the DB — this is a soft delete, not Location.delete()
        self.assertTrue(Location.objects.filter(pk=location.pk).exists())


class PickupModelTests(TestCase):
    def setUp(self):
        self.location = Location.objects.create(
            name="Test Place", latitude=Decimal("1.0"), longitude=Decimal("1.0")
        )

    def test_default_status_is_pending(self):
        pickup = Pickup.objects.create(location=self.location)
        self.assertEqual(pickup.status, Pickup.STATUS_PENDING)

    def test_is_paid_reflects_paid_at(self):
        pickup = Pickup.objects.create(location=self.location)
        self.assertFalse(pickup.is_paid)
        pickup.paid_at = timezone.now()
        pickup.save()
        self.assertTrue(pickup.is_paid)

    def test_items_total_sums_pickup_items(self):
        pickup = Pickup.objects.create(location=self.location)
        item_a = Item.objects.create(name="Shirt", item_category=Item.CATEGORY_IRONING, price=20)
        item_b = Item.objects.create(name="Trousers", item_category=Item.CATEGORY_IRONING, price=30)
        PickupItem.objects.create(pickup=pickup, item=item_a, quantity=2, price=20)  # 40
        PickupItem.objects.create(pickup=pickup, item=item_b, quantity=1, price=30)  # 30
        self.assertEqual(pickup.items_total, 70)

    def test_items_total_is_zero_with_no_items(self):
        pickup = Pickup.objects.create(location=self.location)
        self.assertEqual(pickup.items_total, 0)

    def test_str_includes_location_and_status(self):
        pickup = Pickup.objects.create(location=self.location)
        self.assertIn(self.location.name, str(pickup))
        self.assertIn("Pending", str(pickup))


class ItemModelTests(TestCase):
    def test_unique_together_name_and_category(self):
        Item.objects.create(name="Shirt", item_category=Item.CATEGORY_IRONING, price=20)
        with self.assertRaises(Exception):
            # Same name + same category should violate unique_together.
            Item.objects.create(name="Shirt", item_category=Item.CATEGORY_IRONING, price=25)

    def test_same_name_different_category_is_allowed(self):
        Item.objects.create(name="Shirt", item_category=Item.CATEGORY_IRONING, price=20)
        item2 = Item.objects.create(name="Shirt", item_category=Item.CATEGORY_DRYCLEANING, price=50)
        self.assertEqual(Item.objects.filter(name="Shirt").count(), 2)
        self.assertEqual(item2.price, 50)


class PickupItemModelTests(TestCase):
    def test_total_is_price_times_quantity(self):
        location = Location.objects.create(
            name="Test Place", latitude=Decimal("1.0"), longitude=Decimal("1.0")
        )
        pickup = Pickup.objects.create(location=location)
        item = Item.objects.create(name="Shirt", item_category=Item.CATEGORY_IRONING, price=20)
        pickup_item = PickupItem.objects.create(pickup=pickup, item=item, quantity=3, price=20)
        self.assertEqual(pickup_item.total, 60)


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------

class LocationFormTests(TestCase):
    def test_valid_data(self):
        form = LocationForm(data={
            "name": "Green Valley Apartments",
            "house_name": "House No. 24",
            "phone": "+919876543210",
            "maps_url": "https://www.google.com/maps/@9.9312328,76.2673041,17z",
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_missing_required_name_is_invalid(self):
        form = LocationForm(data={
            "latitude": "9.9312328",
            "longitude": "76.2673041",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_optional_fields_can_be_blank(self):
        form = LocationForm(data={
            "name": "Bare Minimum Place",
            "maps_url": "https://www.google.com/maps/@1.0,1.0,17z",
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_photo_upload(self):
        form = LocationForm(
            data={
                "name": "Photo Place",
                "maps_url": "https://www.google.com/maps/@1.0,1.0,17z",
            },
            files={"photo": make_test_photo()},
        )
        self.assertTrue(form.is_valid(), form.errors)


class PickupFormTests(TestCase):
    def test_valid_with_datetime_local_format(self):
        form = PickupForm(data={
            "status": Pickup.STATUS_PENDING,
            "picked_up_at": "2026-07-11T16:30",
            "delivered_at": "",
            "note": "Handle with care",
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_blank_dates_are_allowed(self):
        form = PickupForm(data={
            "status": Pickup.STATUS_PENDING,
            "picked_up_at": "",
            "delivered_at": "",
            "note": "",
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_space_separated_datetime_is_rejected(self):
        # Django accepts both "T" and space-separated datetimes here.
        form = PickupForm(data={
            "status": Pickup.STATUS_PENDING,
            "picked_up_at": "2026-07-11 16:30",  # space, not "T"
            "delivered_at": "",
            "note": "",
        })
        self.assertTrue(form.is_valid(), form.errors)


# ---------------------------------------------------------------------------
# Views — shared setup
# ---------------------------------------------------------------------------

class AuthenticatedViewTestCase(TestCase):
    """Base class that logs a user in for tests that need auth."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="tester", password="pass1234", is_staff=True
        )
        self.client.login(username="tester", password="pass1234")
        self.location = Location.objects.create(
            name="Green Valley Apartments",
            latitude=Decimal("9.9312328"),
            longitude=Decimal("76.2673041"),
            house_name="House No. 24",
        )


# ---------------------------------------------------------------------------
# Auth gate — spot check that key views require login
# ---------------------------------------------------------------------------

class LoginRequiredTests(TestCase):
    def setUp(self):
        self.location = Location.objects.create(
            name="Test Place", latitude=Decimal("1.0"), longitude=Decimal("1.0")
        )
        self.pickup = Pickup.objects.create(location=self.location)

    def assertRedirectsToLogin(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_home_requires_login(self):
        self.assertRedirectsToLogin(reverse("location_list"))

    def test_location_create_requires_login(self):
        self.assertRedirectsToLogin(reverse("location_add"))

    def test_location_detail_requires_login(self):
        self.assertRedirectsToLogin(reverse("location_detail", args=[self.location.pk]))

    def test_location_edit_requires_login(self):
        self.assertRedirectsToLogin(reverse("location_edit", args=[self.location.pk]))

    def test_location_map_requires_login(self):
        self.assertRedirectsToLogin(reverse("location_map"))

    def test_add_pickup_items_requires_login(self):
        self.assertRedirectsToLogin(reverse("add_pickup_items", args=[self.pickup.pk]))

    def test_remove_pickup_item_requires_login(self):
        item = Item.objects.create(name="X", item_category=Item.CATEGORY_IRONING, price=1)
        pi = PickupItem.objects.create(pickup=self.pickup, item=item, quantity=1, price=1)
        self.assertRedirectsToLogin(reverse("remove_pickup_item", args=[pi.pk]))

    def test_mark_pickup_paid_requires_login(self):
        self.assertRedirectsToLogin(reverse("mark_pickup_paid", args=[self.pickup.pk]))

    def test_all_pickups_requires_login(self):
        self.assertRedirectsToLogin(reverse("all_pickups"))

    def test_quick_add_pickup_requires_login(self):
        self.assertRedirectsToLogin(reverse("quick_add_pickup", args=[self.location.pk]))

    def test_set_pickup_status_requires_login(self):
        self.assertRedirectsToLogin(
            reverse("set_pickup_status", args=[self.pickup.pk, Pickup.STATUS_PICKED_UP])
        )

    def test_pickup_detail_is_not_login_gated(self):
        response = self.client.get(reverse("pickup_detail", args=[self.pickup.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)


# ---------------------------------------------------------------------------
# Location views
# ---------------------------------------------------------------------------

class LocationListViewTests(AuthenticatedViewTestCase):
    def test_lists_only_active_locations(self):
        inactive = Location.objects.create(
            name="Inactive Place", latitude=Decimal("1.0"), longitude=Decimal("1.0"),
            is_active=False,
        )
        response = self.client.get(reverse("location_list"))
        self.assertEqual(response.status_code, 200)
        locations = list(response.context["locations"])
        self.assertIn(self.location, locations)
        self.assertNotIn(inactive, locations)


class LocationCreateViewTests(AuthenticatedViewTestCase):
    def test_get_renders_form(self):
        response = self.client.get(reverse("location_add"))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context["form"], LocationForm)

    def test_post_valid_data_creates_location(self):
        response = self.client.post(reverse("location_add"), data={
            "name": "New Place",
            "house_name": "",
            "phone": "",
            "maps_url": "https://www.google.com/maps/@2.0,2.0,17z",
        })
        self.assertRedirects(response, reverse("location_list"))
        self.assertTrue(Location.objects.filter(name="New Place").exists())

    def test_post_invalid_data_rerenders_with_errors(self):
        response = self.client.post(reverse("location_add"), data={"name": ""})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())
        self.assertFalse(Location.objects.filter(name="").exists())


class LocationDetailViewTests(AuthenticatedViewTestCase):
    def test_get_renders_location(self):
        response = self.client.get(reverse("location_detail", args=[self.location.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["location"], self.location)

    def test_post_delete_deactivates_not_deletes(self):
        response = self.client.post(
            reverse("location_detail", args=[self.location.pk]),
            data={"_method": "delete"},
        )
        self.assertRedirects(response, reverse("location_list"))
        self.location.refresh_from_db()
        self.assertFalse(self.location.is_active)
        # Row still exists — soft delete, not a real delete.
        self.assertTrue(Location.objects.filter(pk=self.location.pk).exists())

    def test_get_404_for_missing_location(self):
        response = self.client.get(reverse("location_detail", args=[999999]))
        self.assertEqual(response.status_code, 404)


class LocationEditViewTests(AuthenticatedViewTestCase):
    def test_post_valid_data_updates_location(self):
        response = self.client.post(
            reverse("location_edit", args=[self.location.pk]),
            data={
                "name": "Renamed Place",
                "house_name": "",
                "phone": "",
                "latitude": "3.0",
                "longitude": "3.0",
            },
        )
        self.assertRedirects(response, reverse("location_detail", args=[self.location.pk]))
        self.location.refresh_from_db()
        self.assertEqual(self.location.name, "Renamed Place")

    def test_get_prefills_form_with_instance(self):
        response = self.client.get(reverse("location_edit", args=[self.location.pk]))
        self.assertEqual(response.context["form"].instance, self.location)


class LocationMapViewTests(AuthenticatedViewTestCase):
    def test_excludes_locations_without_coordinates(self):
        # latitude/longitude are non-nullable on the model, so this mostly
        # confirms the view's query doesn't error and returns active,
        # coordinate-bearing locations.
        response = self.client.get(reverse("location_map"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.location, response.context["locations"])


# ---------------------------------------------------------------------------
# Pickup list / create (per-location)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Pickup detail (view / edit / delete)
# ---------------------------------------------------------------------------

class PickupDetailViewTests(AuthenticatedViewTestCase):
    def setUp(self):
        super().setUp()
        self.location = Location.objects.create(
            name="Green Valley Apartments", latitude=Decimal("1.0"), longitude=Decimal("1.0")
        )
        self.pickup = Pickup.objects.create(location=self.location)

    def test_get_renders_pickup_with_items_context(self):
        response = self.client.get(reverse("pickup_detail", args=[self.pickup.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pickup"], self.pickup)
        self.assertEqual(response.context["location"], self.location)
        self.assertIn("dry_items", response.context)
        self.assertIn("iron_items", response.context)
        self.assertIn("pickup_items", response.context)

    def test_post_delete_removes_pickup_and_redirects_to_location(self):
        response = self.client.post(
            reverse("pickup_detail", args=[self.pickup.pk]),
            data={"_method": "delete"},
        )
        self.assertRedirects(response, reverse("all_pickups"))
        self.assertTrue(Pickup.objects.filter(pk=self.pickup.pk).exists())
        self.pickup.refresh_from_db()
        self.assertEqual(self.pickup.status, Pickup.STATUS_CANCELLED)

    def test_post_edit_updates_pickup(self):
        response = self.client.post(
            reverse("pickup_detail", args=[self.pickup.pk]),
            data={
                "status": Pickup.STATUS_PICKED_UP,
                "picked_up_at": "2026-07-11T16:30",
                "delivered_at": "",
                "note": "Updated note",
            },
        )
        self.assertRedirects(response, reverse("pickup_detail", args=[self.pickup.pk]))
        self.pickup.refresh_from_db()
        self.assertEqual(self.pickup.status, Pickup.STATUS_PICKED_UP)
        self.assertEqual(self.pickup.note, "Updated note")

    def test_post_invalid_edit_reshows_form_with_errors(self):
        response = self.client.post(
            reverse("pickup_detail", args=[self.pickup.pk]),
            data={
                "status": "not-a-real-status",
                "picked_up_at": "",
                "delivered_at": "",
                "note": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["show_edit_modal"])

    def test_get_404_for_missing_pickup(self):
        response = self.client.get(reverse("pickup_detail", args=[999999]))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Pickup items
# ---------------------------------------------------------------------------

class AddPickupItemsViewTests(AuthenticatedViewTestCase):
    def setUp(self):
        super().setUp()
        self.pickup = Pickup.objects.create(location=self.location)

    def test_creates_new_item_and_pickup_item_with_given_price(self):
        response = self.client.post(
            reverse("add_pickup_items", args=[self.pickup.pk]),
            data={
                "item_name": ["Shirt"],
                "item_category": [Item.CATEGORY_IRONING],
                "quantity": ["2"],
                "price": ["25"],
            },
        )
        self.assertRedirects(response, reverse("pickup_detail", args=[self.pickup.pk]))

        item = Item.objects.get(name="shirt", item_category=Item.CATEGORY_IRONING)
        self.assertEqual(item.price, 25)  # new item takes the submitted price

        pickup_item = PickupItem.objects.get(pickup=self.pickup, item=item)
        self.assertEqual(pickup_item.quantity, 2)
        self.assertEqual(pickup_item.price, 25)

    def test_blank_price_falls_back_to_existing_catalog_price(self):
        Item.objects.create(name="trousers", item_category=Item.CATEGORY_DRYCLEANING, price=50)
        response = self.client.post(
            reverse("add_pickup_items", args=[self.pickup.pk]),
            data={
                "item_name": ["Trousers"],
                "item_category": [Item.CATEGORY_DRYCLEANING],
                "quantity": ["1"],
                "price": [""],  # left blank
            },
        )
        self.assertRedirects(response, reverse("pickup_detail", args=[self.pickup.pk]))
        pickup_item = PickupItem.objects.get(pickup=self.pickup, item__name="trousers")
        self.assertEqual(pickup_item.price, 50)

    def test_multiple_rows_in_one_submission(self):
        response = self.client.post(
            reverse("add_pickup_items", args=[self.pickup.pk]),
            data={
                "item_name": ["Shirt", "Trousers"],
                "item_category": [Item.CATEGORY_IRONING, Item.CATEGORY_IRONING],
                "quantity": ["1", "3"],
                "price": ["20", "15"],
            },
        )
        self.assertRedirects(response, reverse("pickup_detail", args=[self.pickup.pk]))
        self.assertEqual(self.pickup.items.count(), 2)

    def test_blank_row_names_are_skipped(self):
        response = self.client.post(
            reverse("add_pickup_items", args=[self.pickup.pk]),
            data={
                "item_name": ["", "Shirt"],
                "item_category": [Item.CATEGORY_IRONING, Item.CATEGORY_IRONING],
                "quantity": ["1", "1"],
                "price": ["10", "20"],
            },
        )
        self.assertEqual(self.pickup.items.count(), 1)

    def test_invalid_category_defaults_to_drycleaning(self):
        response = self.client.post(
            reverse("add_pickup_items", args=[self.pickup.pk]),
            data={
                "item_name": ["Mystery Item"],
                "item_category": ["not-a-real-category"],
                "quantity": ["1"],
                "price": ["10"],
            },
        )
        item = Item.objects.get(name="mystery item")
        self.assertEqual(item.item_category, Item.CATEGORY_DRYCLEANING)

    def test_no_items_entered_shows_error_message(self):
        response = self.client.post(
            reverse("add_pickup_items", args=[self.pickup.pk]),
            data={"item_name": [""], "item_category": ["d"], "quantity": [""], "price": [""]},
            follow=True,
        )
        messages = list(response.context["messages"])
        self.assertTrue(any("No items were entered" in str(m) for m in messages))


class RemovePickupItemViewTests(AuthenticatedViewTestCase):
    def test_removes_pickup_item_and_redirects(self):
        pickup = Pickup.objects.create(location=self.location)
        item = Item.objects.create(name="Shirt", item_category=Item.CATEGORY_IRONING, price=20)
        pickup_item = PickupItem.objects.create(pickup=pickup, item=item, quantity=1, price=20)

        response = self.client.post(reverse("remove_pickup_item", args=[pickup_item.pk]))
        self.assertRedirects(response, reverse("pickup_detail", args=[pickup.pk]))
        self.assertFalse(PickupItem.objects.filter(pk=pickup_item.pk).exists())

    def test_404_for_missing_pickup_item(self):
        response = self.client.post(reverse("remove_pickup_item", args=[999999]))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

class MarkPickupPaidViewTests(AuthenticatedViewTestCase):
    def setUp(self):
        super().setUp()
        self.pickup = Pickup.objects.create(location=self.location)

    def test_valid_payment_marks_pickup_paid(self):
        response = self.client.post(
            reverse("mark_pickup_paid", args=[self.pickup.pk]),
            data={"payment_method": Pickup.PAYMENT_UPI, "amount": "150"},
        )
        self.assertRedirects(response, reverse("pickup_detail", args=[self.pickup.pk]))
        self.pickup.refresh_from_db()
        self.assertTrue(self.pickup.is_paid)
        self.assertEqual(self.pickup.payment_method, Pickup.PAYMENT_UPI)
        self.assertEqual(self.pickup.amount_paid, 150)
        self.assertIsNotNone(self.pickup.paid_at)

    def test_decimal_amount_is_rounded_down_to_int(self):
        response = self.client.post(
            reverse("mark_pickup_paid", args=[self.pickup.pk]),
            data={"payment_method": Pickup.PAYMENT_CASH, "amount": "150.75"},
        )
        self.pickup.refresh_from_db()
        self.assertEqual(self.pickup.amount_paid, 150)

    def test_missing_amount_does_not_mark_paid(self):
        response = self.client.post(
            reverse("mark_pickup_paid", args=[self.pickup.pk]),
            data={"payment_method": Pickup.PAYMENT_UPI, "amount": ""},
        )
        self.pickup.refresh_from_db()
        self.assertFalse(self.pickup.is_paid)

    def test_invalid_payment_method_does_not_mark_paid(self):
        response = self.client.post(
            reverse("mark_pickup_paid", args=[self.pickup.pk]),
            data={"payment_method": "bitcoin", "amount": "100"},
        )
        self.pickup.refresh_from_db()
        self.assertFalse(self.pickup.is_paid)

    def test_non_numeric_amount_does_not_crash_and_does_not_mark_paid(self):
        response = self.client.post(
            reverse("mark_pickup_paid", args=[self.pickup.pk]),
            data={"payment_method": Pickup.PAYMENT_UPI, "amount": "not-a-number"},
        )
        self.assertEqual(response.status_code, 302)  # redirects rather than 500
        self.pickup.refresh_from_db()
        self.assertFalse(self.pickup.is_paid)
        self.assertIsNone(self.pickup.payment_method)
        self.assertIsNone(self.pickup.amount_paid)
        self.assertIsNone(self.pickup.paid_at)
        self.assertEqual(self.pickup.status, Pickup.STATUS_PENDING)


# ---------------------------------------------------------------------------
# All pickups (list + pagination + status filter)
# ---------------------------------------------------------------------------

class AllPickupsViewTests(AuthenticatedViewTestCase):
    def test_excludes_delivered_by_default(self):
        pending = Pickup.objects.create(location=self.location, status=Pickup.STATUS_PENDING)
        delivered = Pickup.objects.create(location=self.location, status=Pickup.STATUS_DELIVERED)

        response = self.client.get(reverse("all_pickups"))
        pickups = list(response.context["pickups"])
        self.assertIn(pending, pickups)
        self.assertNotIn(delivered, pickups)
        self.assertFalse(response.context["show_delivered"])

    def test_show_delivered_includes_delivered(self):
        delivered = Pickup.objects.create(location=self.location, status=Pickup.STATUS_DELIVERED)
        response = self.client.get(reverse("all_pickups"), {"show_delivered": "1"})
        pickups = list(response.context["pickups"])
        self.assertIn(delivered, pickups)
        self.assertTrue(response.context["show_delivered"])

    def test_pagination_splits_across_pages(self):
        for i in range(55):
            Pickup.objects.create(location=self.location, status=Pickup.STATUS_PENDING)

        page1 = self.client.get(reverse("all_pickups"))
        self.assertEqual(len(page1.context["pickups"]), 50)
        self.assertEqual(page1.context["page_obj"].paginator.num_pages, 2)

        page2 = self.client.get(reverse("all_pickups"), {"page": 2})
        self.assertEqual(len(page2.context["pickups"]), 5)

    def test_pending_pickup_shows_only_mark_picked_up_button(self):
        Pickup.objects.create(location=self.location, status=Pickup.STATUS_PENDING)

        response = self.client.get(reverse("all_pickups"))
        self.assertContains(response, 'aria-label="Mark as picked up"')
        self.assertNotContains(response, 'aria-label="Mark as delivered"')

    def test_picked_up_pickup_shows_only_mark_delivered_button(self):
        Pickup.objects.create(location=self.location, status=Pickup.STATUS_PICKED_UP)

        response = self.client.get(reverse("all_pickups"))
        self.assertContains(response, 'aria-label="Mark as delivered"')
        self.assertNotContains(response, 'aria-label="Mark as picked up"')


# ---------------------------------------------------------------------------
# Quick add pickup (with Telegram call mocked out — no real network calls)
# ---------------------------------------------------------------------------

class QuickAddPickupViewTests(AuthenticatedViewTestCase):
    @patch("myapp.views._telegram_enabled", return_value=True)
    @patch("myapp.utils.requests.post")
    def test_creates_blank_pickup_and_redirects(self, mock_post, mock_enabled):
        count_before = Pickup.objects.count()
        response = self.client.post(reverse("quick_add_pickup", args=[self.location.pk]))
        self.assertRedirects(response, reverse("all_pickups"))
        self.assertEqual(Pickup.objects.count(), count_before + 1)

        pickup = Pickup.objects.latest("created_at")
        self.assertEqual(pickup.location, self.location)
        self.assertEqual(pickup.status, Pickup.STATUS_PENDING)
        self.assertIsNone(pickup.picked_up_at)
        mock_post.assert_called_once()

    @patch("myapp.views._telegram_enabled", return_value=False)
    @patch("myapp.utils.requests.post")
    def test_skips_telegram_when_disabled(self, mock_post, mock_enabled):
        response = self.client.post(reverse("quick_add_pickup", args=[self.location.pk]))
        self.assertRedirects(response, reverse("all_pickups"))
        mock_post.assert_not_called()

    @patch("myapp.views._telegram_enabled", return_value=True)
    @patch("myapp.utils.requests.post")
    def test_telegram_failure_does_not_break_pickup_creation(self, mock_post, mock_enabled):
        import requests as requests_module
        mock_post.side_effect = requests_module.RequestException("network down")

        response = self.client.post(reverse("quick_add_pickup", args=[self.location.pk]))
        self.assertRedirects(response, reverse("all_pickups"))
        self.assertTrue(
            Pickup.objects.filter(location=self.location).exists(),
            "Pickup should still be created even if the Telegram call fails.",
        )

    @patch("myapp.views._telegram_enabled", return_value=True)
    @patch("myapp.utils.requests.post")
    def test_404_for_missing_location(self, mock_post, mock_enabled):
        response = self.client.post(reverse("quick_add_pickup", args=[999999]))
        self.assertEqual(response.status_code, 404)
        mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# Set pickup status (quick action buttons)
# ---------------------------------------------------------------------------

class SetPickupStatusViewTests(AuthenticatedViewTestCase):
    def setUp(self):
        super().setUp()
        self.pickup = Pickup.objects.create(location=self.location)

    def test_marks_picked_up_and_autofills_picked_up_at(self):
        self.assertIsNone(self.pickup.picked_up_at)
        response = self.client.post(
            reverse("set_pickup_status", args=[self.pickup.pk, Pickup.STATUS_PICKED_UP])
        )
        self.assertEqual(response.status_code, 302)
        self.pickup.refresh_from_db()
        self.assertEqual(self.pickup.status, Pickup.STATUS_PICKED_UP)
        self.assertIsNotNone(self.pickup.picked_up_at)

    def test_marks_delivered_and_autofills_delivered_at(self):
        response = self.client.post(
            reverse("set_pickup_status", args=[self.pickup.pk, Pickup.STATUS_DELIVERED])
        )
        self.pickup.refresh_from_db()
        self.assertEqual(self.pickup.status, Pickup.STATUS_DELIVERED)
        self.assertIsNotNone(self.pickup.delivered_at)

    def test_does_not_overwrite_existing_picked_up_at(self):
        fixed_time = timezone.now() - timedelta(days=1)
        self.pickup.picked_up_at = fixed_time
        self.pickup.save()

        self.client.post(
            reverse("set_pickup_status", args=[self.pickup.pk, Pickup.STATUS_PICKED_UP])
        )
        self.pickup.refresh_from_db()
        self.assertEqual(self.pickup.picked_up_at, fixed_time)

    def test_invalid_status_value_is_rejected(self):
        response = self.client.post(
            reverse("set_pickup_status", args=[self.pickup.pk, "cancelled"])
        )
        self.assertEqual(response.status_code, 302)
        self.pickup.refresh_from_db()
        self.assertEqual(self.pickup.status, Pickup.STATUS_PENDING)  # unchanged


# ---------------------------------------------------------------------------
# Backup media
# ---------------------------------------------------------------------------

class BackupMediaViewTests(TestCase):
    def test_returns_a_zip_file(self):
        with tempfile.TemporaryDirectory() as media_root, \
             tempfile.TemporaryDirectory() as base_dir:
            with override_settings(MEDIA_ROOT=media_root, BASE_DIR=base_dir):
                response = self.client.get(reverse("backup_media"))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "application/zip")
                self.assertIn("attachment", response["Content-Disposition"])


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------

class AuthViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass1234")

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    def test_valid_login_redirects_authenticated_users_away(self):
        self.client.login(username="tester", password="pass1234")
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 302)  # redirect_authenticated_user=True

    def test_logout_requires_post(self):
        self.client.login(username="tester", password="pass1234")
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 302)
        # Session should be cleared — a subsequent authenticated-only view
        # should now redirect to login.
        response = self.client.get(reverse("location_list"))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('location_list')}"
        )
