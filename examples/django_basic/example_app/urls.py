from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.products, name='products'),
    path('slow/', views.slow_operation, name='slow_operation'),
    path('error/', views.error_example, name='error_example'),
    path('user/<int:user_id>/', views.user_profile, name='user_profile'),
]