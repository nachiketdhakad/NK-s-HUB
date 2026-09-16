from django.contrib import admin
from .models import (
    FoodItem, Customer, Reservation, Order, OrderItem, FoodImage, Review,
     Preference, Outlet, Address, UserProfile,
)

admin.site.register(Preference)


class FoodImageInline(admin.TabularInline):
    model = FoodImage
    extra = 1

@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_popular')
    list_filter = ('category', 'preferences')
    filter_horizontal = ('preferences',)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'food', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('food__name', 'user__username', 'comment')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'phone')


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'date', 'time', 'people')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'phone', 'payment_method', 'total_price', 'status', 'created_at')
    list_filter = ('status', 'payment_method')
    search_fields = ('customer_name', 'phone', 'address')


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'food_item', 'quantity', 'price')


@admin.register(Outlet)
class OutletAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'address', 'latitude', 'longitude', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'address')


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'full_name', 'phone_number', 'pincode', 'area_name', 'is_active')
    list_filter = ('area_name', 'is_active')
    search_fields = ('full_name', 'phone_number', 'pincode', 'user__username')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'phone')
    search_fields = ('user__username', 'phone')