from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('menu/', views.menu, name='menu'),
    path('login/', views.login_view, name='login'),
    path('about/', views.about_view, name='about'),
    path('food/<int:pk>/', views.food_detail, name='food_detail'),
    path('upload/', views.upload_food, name='upload_file'),

    # Cart
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:pk>/<str:action>/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:pk>/', views.remove_from_cart, name='remove_from_cart'),

    # Checkout / Orders
    path('checkout/', views.checkout_view, name='checkout'),
    path('order-success/<int:order_id>/', views.order_success, name='order_success'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('order/<int:order_id>/cancel/', views.cancel_order, name='cancel_order'),
    path('order/<int:order_id>/update-address/', views.update_order_address, name='update_order_address'),
    path('buy-now/<int:pk>/', views.buy_now, name='buy_now'),

    # Auth / Account
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('my-account/', views.my_account, name='my_account'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),

    # Address / Delivery / Payment
    path('set-active-address/<int:address_id>/', views.set_active_address, name='set_active_address'),
    path('add-address/', views.add_address, name='add_address'),
    path('payment/', views.payment_view, name='payment'),
    path('confirm-payment/', views.confirm_payment, name='confirm_payment'),
    path('check-pincode/', views.check_pincode, name='check_pincode'),
    path('nearest-zone/', views.nearest_zone, name='nearest_zone'),
    path('nearest-outlet/', views.nearest_outlet, name='nearest_outlet'),

    # Search
    path('search/', views.search_page, name='search_page'),
    path('search-suggest/', views.search_suggest, name='search_suggest'),

    # Favourites / Addresses / Help
    path('favourites/', views.favourites_view, name='favourites'),
    path('favourite/toggle/<int:pk>/', views.toggle_favourite, name='toggle_favourite'),
    path('addresses/', views.addresses_view, name='addresses'),
    path('help/', views.help_page, name='help'),

    # Misc
    path('contact/', views.contact, name='contact'),
    path('sustainability/', views.sustainability, name='sustainability'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

