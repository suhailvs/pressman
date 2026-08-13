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
    
    path("pickups/<int:pk>/", views.pickup_detail, name="pickup_detail"),
    path("pickups/", views.all_pickups, name="all_pickups"),
    path("pickups/<int:pk>/status/<str:status>/", views.set_pickup_status, name="set_pickup_status"),
    path("locations/<int:pk>/pickups/quick-add/", views.quick_add_pickup, name="quick_add_pickup"),
    path("pickups/<int:pk>/paid/", views.mark_pickup_paid, name="mark_pickup_paid"),
    path("pickups/<int:pk>/items/add/", views.add_pickup_items, name="add_pickup_items"),
    path("pickup-items/<int:pk>/remove/", views.remove_pickup_item, name="remove_pickup_item"),
    path("items/create/", views.create_item, name="create_item"),
    
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/mark-attendance/', views.mark_attendance, name='mark_attendance'),
    path('staff/add-advance/', views.add_advance, name='add_advance'),
    path('staff/<int:pk>/', views.staff_detail, name='staff_detail'),
    # path('staff/add/', views.add_staff, name='add_staff'),
    # path('staff/<int:employee_id>/', views.staff_detail, name='staff_detail'),
    
    path("backup/", views.backup_media, name="backup_media"),
    path('change-password/', views.change_password, name='change_password'),
    path("login/", views.LocationsLoginView.as_view(), name="login"),
    path("logout/",views.custom_logout, name="logout"), #LogoutView.as_view(next_page="login"), name="logout"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
