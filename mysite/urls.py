from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView
from myapp import views
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='location_list'),
    path("locations/add/", views.location_create, name="location_add"),
    path("locations/<int:pk>/", views.location_detail, name="location_detail"),
    path("locations/<int:pk>/edit/", views.location_edit, name="location_edit"),
    path("locations/map/", views.location_map, name="location_map"),
    path("locations/<int:pk>/pickups/", views.location_pickups, name="location_pickups"),
    path("pickups/<int:pk>/", views.pickup_detail, name="pickup_detail"),
    path("pickups/", views.all_pickups, name="all_pickups"),
    
    path("backup/", views.backup_media, name="backup_media"),
    
    path("login/", views.LocationsLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="login"), name="logout"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
