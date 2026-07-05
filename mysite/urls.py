from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from myapp import views
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='location_list'),
    path("locations/add/", views.location_create, name="location_add"),
    path("locations/<int:pk>/", views.location_detail, name="location_detail"),
    path("locations/<int:pk>/edit/", views.location_edit, name="location_edit"),
    path("locations/map/", views.location_map, name="location_map"),
    path("locations/<int:pk>/orders/", views.location_orders, name="location_orders"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
