from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('upload_profile_picture/', views.upload_profile_picture, name='upload_profile_picture'),
    path('update_profile/', views.update_profile, name='update_profile'),
    path('get_profile/<str:user_id>/', views.get_profile, name='get_profile'),
]

