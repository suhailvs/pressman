from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView
from myapp import views
urlpatterns = [
    path('admin/', admin.site.urls),
    path('activity-history/', views.project_activity_history, name='project_activity_history'),
    path('activity-history/<str:model_name>/<int:history_id>/', views.activity_entry_detail, name='activity_entry_detail'),
    path('', views.list_location, name='list_location'),
    path("locations/add/", views.location_create, name="location_add"),
    path("locations/<int:pk>/", views.location_detail, name="location_detail"),
    path("locations/<int:pk>/edit/", views.location_edit, name="location_edit"),
    path("locations/<int:pk>/balance/", views.update_location_balance, name="update_location_balance"),
    path("locations/map/", views.location_map, name="location_map"),
    
    path("pickups/<int:pk>/", views.view_pickup, name="view_pickup"),
    path("pickups/", views.list_pickup, name="list_pickup"),
    path("pickups/<int:pk>/status/<str:status>/", views.set_pickup_status, name="set_pickup_status"),
    path("locations/<int:pk>/pickups/quick-add/", views.quick_add_pickup, name="quick_add_pickup"),
    path("pickups/<int:pk>/paid/", views.mark_pickup_paid, name="mark_pickup_paid"),
    path("pickups/<int:pk>/add-items/", views.add_pickup_items_page, name="add_pickup_items_page"),
    path("pickups/<int:pk>/items/add/", views.add_pickup_items, name="add_pickup_items"),
    path("pickup-items/<int:pk>/remove/", views.remove_pickup_item, name="remove_pickup_item"),
    path("items/create/", views.create_item, name="create_item"),
    path("items/<int:pk>/update-price/", views.update_item_price, name="update_item_price"),
    path('staff/', views.list_staff, name='list_staff'),
    path('staff/mark-attendance/', views.mark_attendance, name='mark_attendance'),
    path('staff/add-advance/', views.add_advance, name='add_advance'),
    path('staff/<int:pk>/', views.view_staff, name='view_staff'),
    path('staff/<int:pk>/attendance/<int:year>/<int:month>/<int:day>/toggle/',
         views.toggle_attendance, name='toggle_attendance'),
    path('staff/<int:pk>/wage/update/',
         views.update_wage, name='update_wage'),
    path('staff/<int:pk>/advances/<int:advance_pk>/delete/',
         views.delete_advance, name='delete_advance'),
    path('expenses/', views.list_expense, name='list_expense'),
    path('expenses/add/', views.add_expense, name='add_expense'),
    path('expenses/<int:pk>/delete/', views.delete_expense, name='delete_expense'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/daily/', views.daily_dashboard, name='daily_dashboard'),
    # path('staff/add/', views.add_staff, name='add_staff'),
    # path('staff/<int:employee_id>/', views.view_staff, name='view_staff'),
    
    path("backup/", views.backup_media, name="backup_media"),
    path('change-password/', views.change_password, name='change_password'),
    path("login/", views.LocationsLoginView.as_view(), name="login"),
    path("logout/",views.custom_logout, name="logout"), #LogoutView.as_view(next_page="login"), name="logout"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
