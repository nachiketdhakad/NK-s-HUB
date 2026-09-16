from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView  # <-- इसे इम्पोर्ट करें

from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from .models import FoodItem, Order, OrderItem, Review, UserProfile


urlpatterns = [
    path('admin/', admin.site.urls),
    # सीधे home.html पेज को रूट (होम) URL पर चलाएं:
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
]
from django.shortcuts import render

def index(request):
    return render(request, 'index.html')   # 👈 file food/templates/index.html me honi chahiye


def login_view(request):
    return render(request, 'login.html')


def order(request):
    return render(request, 'order.html')

def about(request):
    return render(request, 'about.html')


def cart_view(request):
    return render(request, 'food/cart.html')

