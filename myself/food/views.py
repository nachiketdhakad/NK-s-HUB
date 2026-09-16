from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import JsonResponse
from decimal import Decimal
from .models import FoodItem, Order, OrderItem, Review, UserProfile, Address, Outlet, PINCODE_ZONES
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
import math
from .models import FoodItem, Order, OrderItem, Review, UserProfile, Address, Outlet, Favourite, PINCODE_ZONES
from django.shortcuts import render, redirect
from django.contrib import messages

# ---------------- OUTLET / DELIVERY LOGIC (no external API needed) ----------------

AVG_SPEED_KMPH = 25       # average delivery speed assumption
PREP_TIME_MIN = 10        # food prep time added to every estimate


def haversine_km(lat1, lng1, lat2, lng2):
    """Do coordinates ke beech ki straight-line distance (km) nikalta hai."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_nearest_outlet(user_lat, user_lng):
    """Sabhi active outlets me se user ke sabse pass wala outlet dhundta hai (seedha coordinate-distance se)."""
    outlets = list(Outlet.objects.filter(is_active=True))
    if not outlets or user_lat is None or user_lng is None:
        return None, ""

    try:
        user_lat = float(user_lat)
        user_lng = float(user_lng)
    except (TypeError, ValueError):
        return None, ""

    best_outlet = None
    best_distance = None

    for outlet in outlets:
        dist = haversine_km(user_lat, user_lng, outlet.latitude, outlet.longitude)
        if best_distance is None or dist < best_distance:
            best_distance = dist
            best_outlet = outlet

    if best_outlet is None:
        return None, ""

    minutes = round((best_distance / AVG_SPEED_KMPH) * 60 + PREP_TIME_MIN)
    duration_text = f"{minutes} mins"
    return best_outlet, duration_text


def check_pincode(request):
    """
    AJAX endpoint — Flipkart-style pincode check.
    Address form me pincode type karte hi ye call hoga aur turant bata dega
    delivery available hai ya nahi (page reload/submit se pehle hi).
    """
    pincode = request.GET.get('pincode', '').strip()
    zone = PINCODE_ZONES.get(pincode)

    if zone:
        outlet, duration_text = get_nearest_outlet(zone['lat'], zone['lng'])
        if outlet:
            return JsonResponse({
                "deliverable": True,
                "area_name": zone['name'],
                "outlet_name": outlet.name,
                "duration": duration_text,
            })

    return JsonResponse({
        "deliverable": False,
        "message": "Sorry, we don't deliver to this pincode yet",
    })


def nearest_zone(request):
    """
    GPS-based endpoint — browser se current lat/lng bhejo, ye apne 5 delivery zones me
    se sabse pass wala dhund ke uska pincode return karta hai (koi external API nahi).
    """
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')

    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return JsonResponse({"pincode": None, "message": "Location sahi se nahi mili"})

    MAX_MATCH_KM = 15  # isse dur hai to koi zone match nahi maana jayega

    best_pincode = None
    best_name = None
    best_dist = None

    for pincode, zone in PINCODE_ZONES.items():
        dist = haversine_km(lat, lng, zone['lat'], zone['lng'])
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_pincode = pincode
            best_name = zone['name']

    if best_pincode and best_dist <= MAX_MATCH_KM:
        return JsonResponse({"pincode": best_pincode, "area_name": best_name})

    return JsonResponse({"pincode": None, "message": "Your current location is outside our delivery zones"})


def nearest_outlet(request):
    """AJAX endpoint — checkout page pe saved active address ke liye delivery status dikhane ke liye."""
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')

    outlet, duration_text = get_nearest_outlet(lat, lng)

    if outlet:
        return JsonResponse({
            "outlet_name": outlet.name,
            "outlet_address": outlet.address,
            "duration": duration_text,
        })
    return JsonResponse({"error": "unavailable", "message": "Delivery is not available for this location"}, status=200)


# ---------------- HOME / MENU / FOOD DETAIL ----------------

def home(request):
    items = FoodItem.objects.all()
    return render(request, "food/index.html", {"items": items})


def upload_food(request):
    if request.method == "POST":
        name = request.POST["name"]
        description = request.POST["description"]
        price = request.POST["price"]
        image = request.FILES["image"]

        item = FoodItem(name=name, description=description, price=price, image=image)
        item.save()
    return render(request, "upload.html")


def upload_profile(request):
    return render(request, 'upload.html')


def _matches_query(item_name, query_lower):
    """
    Ek helper function — food item ke naam ko query se match karta hai teen tarike se:
    1. Naam ke andar kahin bhi query mile (icontains jaisa)
    2. Naam query se shuru hota ho (istartswith jaisa)
    3. Naam ke har word ka pehla letter (initials) query se match ho
       jaise 'vcb' ya 'v c b' -> 'Veg Cheese Burger'
    """
    if not query_lower:
        return True

    name_lower = item_name.lower()
    if query_lower in name_lower:
        return True

    initials = ''.join(word[0] for word in item_name.split() if word).lower()
    query_no_space = query_lower.replace(' ', '')
    if initials.startswith(query_no_space):
        return True

    return False


def menu(request):
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()

    popular_items = FoodItem.objects.filter(is_popular=True)
    items = FoodItem.objects.exclude(is_popular=True)

    if category and category.lower() != 'all':
        items = items.filter(category=category)

    if query:
        query_lower = query.lower()
        matched_ids = [item.id for item in items if _matches_query(item.name, query_lower)]
        items = items.filter(id__in=matched_ids)

    cart = request.session.get('cart', {})
    cart_count = sum(cart.values())

    return render(request, 'food/menu.html', {
        'items': items,
        'popular_items': popular_items,
        'cart_count': cart_count,
        'selected_category': category,
        'search_query': query,
    })



def search_page(request):
    """Swiggy/Flipkart jaisa dedicated search page — results yahi page live type karte hi update hote hai (AJAX se)."""
    cart = request.session.get('cart', {})
    cart_count = sum(cart.values())
    return render(request, 'food/search.html', {'cart_count': cart_count})


def search_suggest(request):
    """AJAX endpoint — search page se call hota hai. Naam ke andar/shuru se match karta hai,
    aur naam ke har word ke pehle letter (initials) se bhi match karta hai
    (jaise 'vcb' -> 'Veg Cheese Burger')."""
    query = request.GET.get('q', '').strip()
    results = []

    if query:
        query_lower = query.lower()

        all_items = FoodItem.objects.all()
        matched_items = [
            item for item in all_items
            if _matches_query(item.name, query_lower)
        ][:20]

        for item in matched_items:
            results.append({
                'id': item.id,
                'name': item.name,
                'description': item.description or '',
                'price': str(item.price),
                'discounted_price': str(item.discounted_price()),
                'discount': item.discount,
                'rating': str(item.rating),
                'views': item.views,
                'image_url': item.image.url if item.image else '',
                'category': item.get_category_display() if item.category else '',
                'is_nonveg': item.is_nonveg,
            })

    return JsonResponse({'query': query, 'results': results})


def food_detail(request, pk):
    item = get_object_or_404(FoodItem, pk=pk)

    if request.method == "POST" and 'submit_review' in request.POST:
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.path}")

        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        Review.objects.create(food=item, user=request.user, rating=rating, comment=comment)
        messages.success(request, "Thanks for your review!")
        return redirect('food_detail', pk=pk)

    item.views += 1
    item.save(update_fields=['views'])

    reviews = item.reviews.all().order_by('-created_at')
    gallery_images = item.images.all()
    avg_rating = item.rating
    related_items = FoodItem.objects.filter(category=item.category).exclude(pk=item.pk)[:6]
    cart = request.session.get('cart', {})
    cart_count = sum(cart.values())

    user_fav_ids = []
    if request.user.is_authenticated:
        user_fav_ids = list(
            Favourite.objects.filter(user=request.user).values_list('food_item_id', flat=True)
        )

    return render(request, 'food/food_detail.html', {
        'item': item,
        'reviews': reviews,
        'gallery_images': gallery_images,
        'avg_rating': avg_rating,
        'related_items': related_items,
        'cart_count': cart_count,
        'user_fav_ids': user_fav_ids,
    })




def login_view(request):
    next_url = request.POST.get('next') or request.GET.get('next') or 'menu'

    if request.method == 'POST':
        identifier = request.POST.get('identifier')
        password = request.POST.get('password')

        user = authenticate(request, username=identifier, password=password)
        if user is not None:
            auth_login(request, user)
            return redirect(next_url)

        return render(request, 'food/login.html', {
            'error': 'Email/Phone ya password galat hai.'
        })

    return render(request, 'food/login.html')


def signup_view(request):
    next_url = request.POST.get('next') or request.GET.get('next') or 'menu'

    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password')

        if User.objects.filter(username=username).exists():
            return render(request, 'food/signup.html', {'error': 'Ye username pehle se hai.'})
        if email and User.objects.filter(email__iexact=email).exists():
            return render(request, 'food/signup.html', {'error': 'Ye email pehle se register hai.'})
        if phone and UserProfile.objects.filter(phone=phone).exists():
            return render(request, 'food/signup.html', {'error': 'Ye phone number pehle se register hai.'})

        user = User.objects.create_user(username=username, email=email, password=password)
        UserProfile.objects.create(user=user, phone=phone or None)

        user.backend = 'food.backends.EmailOrPhoneBackend'
        auth_login(request, user)
        return redirect(next_url)

    return render(request, 'food/signup.html')


def logout_view(request):
    auth_logout(request)
    return redirect('home')


def about_view(request):
    outlets = Outlet.objects.filter(is_active=True)
    return render(request, 'food/about.html', {'outlets': outlets})


# ---------------- CART LOGIC (session based) ----------------

def _get_cart(request):
    return request.session.get('cart', {})


def cart_view(request):
    cart = _get_cart(request)
    cart_items = []
    total = Decimal('0')

    for food_id, qty in cart.items():
        try:
            food = FoodItem.objects.get(pk=food_id)
        except FoodItem.DoesNotExist:
            continue
        price = Decimal(str(food.discounted_price()))
        subtotal = price * qty
        total += subtotal
        cart_items.append({
            'food': food,
            'quantity': qty,
            'price': price,
            'subtotal': subtotal,
        })

    recommended_items = FoodItem.objects.exclude(
        pk__in=[item['food'].pk for item in cart_items]
    )[:5]

    context = {
        'cart_items': cart_items,
        'total': total,
        'recommended_items': recommended_items,
    }
    return render(request, 'food/cart.html', context)


def add_to_cart(request, pk):
    food_item = get_object_or_404(FoodItem, pk=pk)
    cart = _get_cart(request)
    key = str(pk)
    qty = int(request.POST.get('quantity', 1)) if request.method == "POST" else 1
    cart[key] = cart.get(key, 0) + qty
    request.session['cart'] = cart
    request.session.modified = True
    cart_count = sum(cart.values())

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'cart_count': cart_count,
            'item_name': food_item.name,
        })

    messages.success(request, f"{food_item.name} added to cart.")
    return redirect('cart')


def update_cart(request, pk, action):
    cart = _get_cart(request)
    key = str(pk)
    qty = int(cart.get(key, 0))

    if action in ('increase', 'inc'):
        qty += 1
    elif action in ('decrease', 'dec'):
        qty -= 1

    if qty <= 0:
        cart.pop(key, None)
    else:
        cart[key] = qty

    request.session['cart'] = cart
    request.session.modified = True
    return redirect('cart')


def remove_from_cart(request, pk):
    cart = _get_cart(request)
    cart.pop(str(pk), None)
    request.session['cart'] = cart
    request.session.modified = True
    return redirect('cart')


# ---------------- ADDRESS LOGIC ----------------

@login_required
def set_active_address(request, address_id):
    Address.objects.filter(user=request.user).update(is_active=False)
    addr = get_object_or_404(Address, id=address_id, user=request.user)
    addr.is_active = True
    addr.save()
    return JsonResponse({'success': True})


@login_required
def add_address(request):
    if request.method == 'POST':
        if Address.objects.filter(user=request.user).count() >= 4:
            return JsonResponse({'success': False, 'error': 'Max 4 addresses allowed'})

        full_name = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        pincode = request.POST.get('pincode', '').strip()
        address_line = request.POST.get('address_line', '').strip()

        if not full_name or not phone_number or not pincode or not address_line:
            return JsonResponse({'success': False, 'error': 'Saari details bharo'})

        zone = PINCODE_ZONES.get(pincode)
        if not zone:
            return JsonResponse({'success': False, 'error': 'Sorry, hum abhi is pincode par deliver nahi karte'})

        Address.objects.filter(user=request.user).update(is_active=False)
        addr = Address.objects.create(
            user=request.user,
            full_name=full_name,
            phone_number=phone_number,
            pincode=pincode,
            area_name=zone['name'],
            address_line=address_line,
            latitude=zone['lat'],
            longitude=zone['lng'],
            is_active=True,
        )
        return JsonResponse({'success': True, 'address_id': addr.id})
    return JsonResponse({'success': False})


# ---------------- CHECKOUT / PAYMENT / ORDER ----------------

def checkout_view(request):
    cart = _get_cart(request)
    if not cart:
        messages.warning(request, "Your cart is empty.")
        return redirect('cart')

    cart_items = []
    total = Decimal('0')
    for food_id, qty in cart.items():
        try:
            food = FoodItem.objects.get(pk=food_id)
        except FoodItem.DoesNotExist:
            continue
        price = Decimal(str(food.discounted_price()))
        subtotal = price * qty
        total += subtotal
        cart_items.append({'food': food, 'quantity': qty, 'price': price, 'subtotal': subtotal})

    delivery_fee = Decimal('20')
    gst_amount = round(total * Decimal('0.05'), 2)
    grand_total = total + delivery_fee + gst_amount

    addresses = []
    active_address = None
    coupon_code = request.POST.get('coupon_code', '').strip().upper()
    if coupon_code == 'SAVE10':
            grand_total = round(grand_total * Decimal('0.9'), 2)
    elif coupon_code == 'FLAT20':
            grand_total = grand_total - Decimal('20')
    prefill_name = ''
    prefill_phone = ''
    if request.user.is_authenticated:
        user_addresses = Address.objects.filter(user=request.user).order_by('-created_at')
        active_address = user_addresses.filter(is_active=True).first()
        addresses = user_addresses[:4]

        # Naam/phone login se auto-fill karne ke liye — user ko dobara type na karna pade
        prefill_name = request.user.get_full_name() or request.user.username
        if hasattr(request.user, 'profile') and request.user.profile.phone:
            prefill_phone = request.user.profile.phone
        elif request.user.username.isdigit():
            # Agar profile me phone save nahi hai, lekin phone se hi login kiya tha, wahi use kar lo
            prefill_phone = request.user.username

    zone_list = [{'pincode': pin, 'name': z['name']} for pin, z in PINCODE_ZONES.items()]

    context = {
        'cart_items': cart_items,
        'total': total,
        'delivery_fee': delivery_fee,
        'gst_amount': gst_amount,
        'grand_total': grand_total,
        'addresses': addresses,
        'active_address': active_address,
        'prefill_name': prefill_name,
        'prefill_phone': prefill_phone,
        'zone_list': zone_list,
    }

    if request.method == "POST":
        if not request.user.is_authenticated:
            messages.warning(request, "Order place karne ke liye login karo.")
            return redirect(f"{reverse('login')}?next={request.path}")

        if not active_address:
            messages.warning(request, "Pehle delivery address select karo.")
            return render(request, 'food/checkout.html', context)

        # Nearest outlet automatically nikalna aur order ke saath assign karna
        outlet, duration_text = get_nearest_outlet(active_address.latitude, active_address.longitude)

        if not outlet:
            messages.warning(request, "Is location par delivery available nahi hai.")
            return render(request, 'food/checkout.html', context)

        payment_method = request.POST.get('payment_method', 'upi')
        if payment_method not in ('upi', 'cod', 'card'):
            payment_method = 'upi'

        # COD sirf ₹1000 tak ke order par allowed hai — isse zyada pe seedha UPI pe switch kar do
        COD_MAX_AMOUNT = Decimal('1000')
        if payment_method == 'cod' and grand_total > COD_MAX_AMOUNT:
            messages.warning(request, "Cash on Delivery is only available for orders under ₹1000. Please choose UPI instead.")
            payment_method = 'upi'

        # COD me pehle hi payment nahi karni, isliye order seedha "Placed" ho jayega.
        # UPI/Card me pehle payment page pe bhejna hai, isliye "Pending Payment" rakha.
        initial_status = "Placed" if payment_method == 'cod' else "Pending Payment"

        order = Order.objects.create(
            customer_name=active_address.full_name,
            phone=active_address.phone_number,
            address=f"{active_address.address_line}, {active_address.area_name} - {active_address.pincode}",
            payment_method=payment_method,
            total_price=grand_total,
            status=initial_status,
            assigned_outlet=outlet,
            estimated_time=duration_text,
        )

        for ci in cart_items:
            OrderItem.objects.create(
                order=order,
                food_item=ci['food'],
                quantity=ci['quantity'],
                price=ci['price'],
            )

        if payment_method == 'cod':
            # COD me koi payment step nahi chahiye — cart clear karke seedha order-success pe bhej do
            request.session['cart'] = {}
            my_orders = request.session.get('my_orders', [])
            my_orders.append(order.id)
            request.session['my_orders'] = my_orders
            request.session.modified = True
            return redirect('order_success', order_id=order.id)

        request.session['pending_order_id'] = order.id
        request.session.modified = True

        return redirect('payment')

    return render(request, 'food/checkout.html', context)


@login_required
def payment_view(request):
    order_id = request.session.get('pending_order_id')
    if not order_id:
        messages.warning(request, "Koi pending order nahi mila.")
        return redirect('checkout')

    order = get_object_or_404(Order, pk=order_id)
    upi_string = f"upi://pay?pa=nkshub@upi&pn=NKsHub&am={order.total_price}&cu=INR"

    return render(request, 'food/payment.html', {
        'order': order,
        'upi_string': upi_string,
        'is_card': order.payment_method == 'card',
    })


@login_required
def confirm_payment(request):
    order_id = request.session.get('pending_order_id')
    if not order_id:
        return redirect('checkout')

    order = get_object_or_404(Order, pk=order_id)
    order.status = "Placed"
    order.save(update_fields=['status'])

    request.session['cart'] = {}
    my_orders = request.session.get('my_orders', [])
    my_orders.append(order.id)
    request.session['my_orders'] = my_orders
    del request.session['pending_order_id']
    request.session.modified = True

    return redirect('order_success', order_id=order.id)


def order_success(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    return render(request, 'food/order_success.html', {'order': order})


def my_orders(request):
    order_ids = request.session.get('my_orders', [])
    orders = Order.objects.filter(id__in=order_ids).order_by('-created_at')

    status_filter = request.GET.get('status', '')
    time_filter = request.GET.get('time', '')
    search_query = request.GET.get('q', '').strip()

    if status_filter:
        orders = orders.filter(status=status_filter)

    if search_query:
        orders = orders.filter(
            Q(id__icontains=search_query) | Q(items__food_item__name__icontains=search_query)
        ).distinct()

    if time_filter == '30days':
        cutoff = timezone.now() - timedelta(days=30)
        orders = orders.filter(created_at__gte=cutoff)
    elif time_filter == 'year':
        orders = orders.filter(created_at__year=timezone.now().year)

    orders_data = []
    for order in orders:
        first_item = order.items.select_related('food_item').first()
        orders_data.append({
            'order': order,
            'preview_image': first_item.food_item.image if first_item and first_item.food_item.image else None,
            'first_item_name': first_item.food_item.name if first_item else '',
            'item_count': order.items.count(),
        })

    return render(request, 'food/my_orders.html', {
        'orders_data': orders_data,
        'status_filter': status_filter,
        'time_filter': time_filter,
        'search_query': search_query,
        'status_choices': Order.STATUS_CHOICES,
    })


def _owns_order(request, order):
    my_order_ids = request.session.get('my_orders', [])
    return order.id in my_order_ids


def order_detail(request, order_id):
    order = get_object_or_404(Order, pk=order_id)

    if not _owns_order(request, order):
        messages.error(request, "You don't have permission to view this order.")
        return redirect('my_orders')

    order_items = OrderItem.objects.filter(order=order)
    can_modify = order.status == 'Placed'

    return render(request, 'food/order_detail.html', {
        'order': order,
        'order_items': order_items,
        'can_modify': can_modify,
    })


def cancel_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id)

    if not _owns_order(request, order):
        messages.error(request, "You don't have permission to cancel this order.")
        return redirect('my_orders')

    if request.method == 'POST':
        if order.status == 'Placed':
            order.status = 'Cancelled'
            order.save(update_fields=['status'])
            messages.success(request, "Order cancelled successfully.")
        else:
            messages.warning(request, "This order can no longer be cancelled.")

    return redirect('order_detail', order_id=order.id)


def update_order_address(request, order_id):
    order = get_object_or_404(Order, pk=order_id)

    if not _owns_order(request, order):
        messages.error(request, "You don't have permission to edit this order.")
        return redirect('my_orders')

    if request.method == 'POST':
        if order.status != 'Placed':
            messages.warning(request, "This order can no longer be edited.")
            return redirect('order_detail', order_id=order.id)

        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()

        if phone:
            order.phone = phone
        if address:
            order.address = address
        order.save(update_fields=['phone', 'address'])
        messages.success(request, "Delivery details updated.")

    return redirect('order_detail', order_id=order.id)


def buy_now(request, pk):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={request.path}")

    food_item = get_object_or_404(FoodItem, pk=pk)
    qty = int(request.POST.get('quantity', 1)) if request.method == "POST" else 1

    cart = _get_cart(request)
    key = str(pk)
    cart[key] = cart.get(key, 0) + qty
    request.session['cart'] = cart
    request.session.modified = True

    return redirect('checkout')


@login_required(login_url='login')
def my_account(request):
    order_ids = request.session.get('my_orders', [])
    orders = Order.objects.filter(id__in=order_ids).order_by('-created_at')

    phone = None
    if hasattr(request.user, 'profile'):
        phone = request.user.profile.phone

    return render(request, 'food/my_account.html', {
        'orders': orders,
        'phone': phone,
    })


@login_required(login_url='login')
def edit_profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        phone = request.POST.get('phone')

        request.user.username = username
        request.user.email = email
        request.user.save()

        profile.phone = phone or None
        profile.save()

        messages.success(request, "Profile updated successfully.")
        return redirect('my_account')

    return render(request, 'food/edit_profile.html', {'profile': profile})


def sustainability(request):
    return render(request, 'food/sustainability.html')


def contact(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        message = request.POST.get("message")

        # abhi ke liye console/terminal me print ho jayega
        # baad me ise email bhejne ya DB me save karne ke liye badal sakte ho
        print(f"New contact message from {name} ({email}): {message}")

        messages.success(request, "Thanks! We'll get back to you soon.")
        return redirect('contact')

    return render(request, 'food/contact.html')

@login_required
def toggle_favourite(request, pk):
    food_item = get_object_or_404(FoodItem, pk=pk)
    fav, created = Favourite.objects.get_or_create(user=request.user, food_item=food_item)
    is_fav = True
    if not created:
        fav.delete()
        is_fav = False

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'is_favourite': is_fav})
    return redirect(request.META.get('HTTP_REFERER', 'menu'))


@login_required
def favourites_view(request):
    favourites = Favourite.objects.filter(user=request.user).select_related('food_item').order_by('-created_at')
    return render(request, 'food/favourites.html', {'favourites': favourites})


@login_required
def add_address(request):
    if request.method == 'POST':
        if Address.objects.filter(user=request.user).count() >= 4:
            return JsonResponse({'success': False, 'error': 'Max 4 addresses allowed'})

        full_name = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        pincode = request.POST.get('pincode', '').strip()
        address_line = request.POST.get('address_line', '').strip()

        if not full_name or not phone_number or not pincode or not address_line:
            return JsonResponse({'success': False, 'error': 'Saari details bharo'})

        # 👇 Phone number validation — exactly 10 digits, sirf numbers
        if not phone_number.isdigit() or len(phone_number) != 10:
            return JsonResponse({'success': False, 'error': 'Phone number 10 digit ka hona chahiye'})

        zone = PINCODE_ZONES.get(pincode)
        if not zone:
            return JsonResponse({'success': False, 'error': 'Sorry, hum abhi is pincode par deliver nahi karte'})

        Address.objects.filter(user=request.user).update(is_active=False)
        addr = Address.objects.create(
            user=request.user,
            full_name=full_name,
            phone_number=phone_number,
            pincode=pincode,
            area_name=zone['name'],
            address_line=address_line,
            latitude=zone['lat'],
            longitude=zone['lng'],
            is_active=True,
        )
        return JsonResponse({'success': True, 'address_id': addr.id})
    return JsonResponse({'success': False})

@login_required
def favourites_view(request):
    favourites = Favourite.objects.filter(user=request.user).select_related('food_item').order_by('-created_at')
    return render(request, 'food/favourites.html', {'favourites': favourites})


@login_required
def addresses_view(request):
    addresses = Address.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'food/addresses.html', {'addresses': addresses})

def help_page(request):
    return render(request, 'food/help.html')




def help_page(request):
    return render(request, 'food/help.html')