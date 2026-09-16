from django.db import models
from django.conf import settings   # 👈 add this import at the top of the file
from django.contrib.auth.models import User
from django.utils.text import slugify


# ---------------- DELIVERY ZONES (pincode based) ----------------
# Indore ki 5 badi/known areas — sirf yehi pincodes delivery list me hai.
# Pincodes verified hai (real). Coordinates approx hai — Outlet coordinates ki tarah
# inhe bhi Google Maps pe "<area name> Indore" search karke ek baar cross-check kar lena.
PINCODE_ZONES = {
    '452010': {'name': 'Vijay Nagar',    'lat': 22.7533, 'lng': 75.8937},
    '452001': {'name': 'Palasia',        'lat': 22.7167, 'lng': 75.8833},
    '452009': {'name': 'Sudama Nagar',   'lat': 22.6984, 'lng': 75.8567},
    '452012': {'name': 'Rajendra Nagar', 'lat': 22.6700, 'lng': 75.8100},
    '452008': {'name': 'Malviya Nagar',  'lat': 22.7450, 'lng': 75.9050},
}


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15)
    pincode = models.CharField(max_length=6)
    area_name = models.CharField(max_length=100, blank=True)  # pincode se auto-fill hota hai
    address_line = models.TextField(help_text="House no, street, landmark")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_active = models.BooleanField(default=False)  # sirf ek hi active rahega
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.area_name} ({self.pincode})"


class Outlet(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    """Admin panel se hi add/edit/delete hoti hai — koi fixed list nahi."""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True, blank=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Preference(models.Model):
    """Admin panel se hi add/edit/delete hoti hai (jaise Veg, Non-Veg, Spicy) — ek food item pe ek se zyada laga sakte ho."""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True, blank=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class FoodItem(models.Model):
         
    CATEGORY_CHOICES = [
    ('burger', 'Burgers'),
    ('pizza', 'Pizza'),
    ('chinese', 'Chinese'),
    ('drink', 'Drinks'),
    ('desserts', 'Desserts'),
    ('rajasthani', 'Rajasthani'),
    ('hot-drinks', 'Hot Drinks'),
    ('cake', 'Cake'),
    ('icecream','icecream'),
    ('sweets', 'Sweets'),
]
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    image = models.ImageField(upload_to='food/', blank=True, null=True)

    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        blank=True,
        null=True,
    )

    preferences = models.ManyToManyField(Preference, blank=True, related_name='food_items')
    ...


    discount = models.PositiveIntegerField(default=0, help_text="Discount % (e.g. 20)")
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=0.0, help_text="e.g. 4.3")
    views = models.PositiveIntegerField(default=0, help_text="Admin se manually bhi edit ho sakta hai")
    is_popular = models.BooleanField(default=False, help_text="Show in Popular Right Now section")

    def discounted_price(self):
        if self.discount:
            return round(float(self.price) * (100 - self.discount) / 100, 2)
        return self.price

    @property
    def is_nonveg(self):
        return self.preferences.filter(slug='nonveg').exists()

    def __str__(self):
        return self.name


class Customer(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return self.name


class Reservation(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    date = models.DateField()
    time = models.TimeField()
    people = models.PositiveIntegerField()

    def __str__(self):
        return f"Reservation {self.id} - {self.customer.name}"


class Order(models.Model):
    PAYMENT_CHOICES = [
        ('cod', 'Cash on Delivery'),
        ('upi', 'UPI'),
        ('card', 'Card'),
    ]
    STATUS_CHOICES = [
        ('Pending Payment', 'Pending Payment'),
        ('Placed', 'Placed'),
        ('On the Way', 'On the Way'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    ]
    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(default='Not provided')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='cod')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Placed")
    total_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    # Nearest-outlet / delivery-time fields
    assigned_outlet = models.ForeignKey(
        Outlet, on_delete=models.SET_NULL, null=True, blank=True
    )
    estimated_time = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"Order #{self.id} - {self.customer_name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    def subtotal(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.food_item.name} x {self.quantity}"


class FoodImage(models.Model):
    food_item = models.ForeignKey(FoodItem, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='food/gallery/')

    def __str__(self):
        return f"Image for {self.food_item.name}"


class Review(models.Model):
    food = models.ForeignKey(FoodItem, related_name='reviews', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    comment = models.TextField()
    rating = models.PositiveSmallIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.food.name} ({self.rating}★)"


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=15, unique=True, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} profile"




class Favourite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favourites')
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'food_item')

    def __str__(self):
        return f"{self.user.username} ♥ {self.food_item.name}"

    