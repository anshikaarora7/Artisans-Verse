import os
import uuid
import base64
import random
import string
from datetime import date

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User as AuthUser
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.mail import send_mail
from django.db import connection
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt

from .models import (
    Admin,
    Brands,
    Cart,
    Category,
    Offers,
    Order,
    OrderItem,
    Payment,
    Product_images,
    Product_sizes,
    Products,
    Shipment,
    User,
)

try:
    import razorpay
    razorpay_client = razorpay.Client(
        auth=(settings.RAZOR_KEY_ID, settings.RAZOR_KEY_SECRET)
    )
except ImportError:
    razorpay = None
    razorpay_client = None

def index(request):
    products_list = list(Products.objects.all())

    for product in products_list:
        size = Product_sizes.objects.filter(prod_id=product.id).first()
        product.price = size.price if size else 0
        random.seed(product.id)
        product.stars = random.choice([1, 2, 3, 3.5, 4, 4.5, 5])

    brands_list = Brands.objects.all()
    categorys = Category.objects.filter(parent_cat__isnull=True, sub_cat__isnull=True)
    context = {
        "products": products_list,
        "brands": brands_list,
        "categorys": categorys,
        "username": (
            (request.user.get_full_name() or request.user.username)
            if request.user.is_authenticated
            else request.session.get("username")
        ),
        "usermail": (
            request.user.email
            if request.user.is_authenticated
            else request.session.get("useremail")
        ),
    }
    return render(request, "web/index.html", context)

def shop_detail(request,prod_id):
    products = get_object_or_404(Products, id=prod_id)
    category=Category.objects.filter(parent_cat=products.parent_cat,sub_cat=products.sub_cat).first()
    sizes=Product_sizes.objects.filter(prod_id=prod_id)
    images=Product_images.objects.filter(prod_id=prod_id)
    brand=get_object_or_404(Brands, id=products.brand)
    pp = Product_sizes.objects.filter(prod_id=prod_id).first()
    products.price=pp.price
    products.brand=brand.name
    print(category.cat_name)
    context={
        "product":products,
        "images":images,
        "sizes":sizes,
        "category":category
    }
    return render(request,"web/product-details.html",context)

def get_size_details(request, size_id):
    try:
        size = Product_sizes.objects.get(id=size_id)
        data = {
            'price': size.price,
            'stock': size.quantity,
        }
        return JsonResponse(data)
    except Product_sizes.DoesNotExist:
        return JsonResponse({'error': 'Size not found'}, status=404)

def shop(request, parent=0, sub=0, subsub=0):
    # Determine which level of category is selected
    if parent != 0 and sub == 0 and subsub == 0:
        products = Products.objects.filter(parent_cat=parent)

    elif parent != 0 and sub != 0 and subsub == 0:
        products = Products.objects.filter(parent_cat=parent, sub_cat=sub)

    elif parent != 0 and sub != 0 and subsub != 0:
        products = Products.objects.filter(parent_cat=parent, sub_cat=sub, sub_sub_cat=subsub)

    else:
        products = Products.objects.all()

    # Convert to list to modify
    products = list(products)

    # Manually attach add_price from ProductSizes
    for product in products:
        size = Product_sizes.objects.filter(prod_id=product.id).first()
        product.price = size.price if size else 0  # Attach price (default to 0 if none)
        
        random.seed(product.id)  # Seed with ID to get consistent randomness per product
        product.stars = random.choice([1,2,3, 3.5, 4, 4.5, 5])

    # Fetch brands
    brands = Brands.objects.all()

    # Fetch categories for sidebar/menu
    if parent != 0:
        categorys = Category.objects.filter(parent_cat=parent, sub_cat__isnull=True)
    else:
        categorys = Category.objects.filter(parent_cat__isnull=True, sub_cat__isnull=True)

    # Pass all data to template
    return render(request, 'web/shop.html', {
        "products": products,
        "brands": brands,
        "categorys": categorys
    })
    
def _get_cart_customer_id(request):
    """Return a consistent customer key for authenticated users or guest sessions."""
    if request.user.is_authenticated:
        return str(request.user.id)
    if request.session.get('userid'):
        return str(request.session.get('userid'))
    if not request.session.session_key:
        request.session.create()
    return f"guest:{request.session.session_key}"


def _merge_guest_cart(request, user, guest_session_key):
    """Move any pending guest cart items into the authenticated user's cart."""
    if not guest_session_key:
        return
    guest_key = f"guest:{guest_session_key}"
    user_key = str(user.id)
    for item in Cart.objects.filter(customer_id=guest_key, status="pending"):
        existing = Cart.objects.filter(
            customer_id=user_key,
            product_id=item.product_id,
            size_id=item.size_id,
            status="pending",
        ).first()
        if existing:
            existing.quantity += item.quantity
            existing.save()
            item.delete()
        else:
            item.customer_id = user_key
            item.save()


def _cart_totals_payload(customer_id):
    cart_items = fetch_cart_details(customer_id=customer_id, status="pending")
    sub_total = sum(int(item[9] or 0) for item in cart_items)
    shipping = 100 if cart_items else 0
    total = sub_total + shipping
    cart_count = sum(int(item[1] or 0) for item in cart_items)
    return cart_items, sub_total, shipping, total, cart_count


def cart(request):
    customer_id = _get_cart_customer_id(request)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == "POST":
        product_id = request.POST.get('prodid')
        size_id = request.POST.get('sizeid')
        try:
            quantity = max(1, int(request.POST.get('quantity', 1)))
        except (TypeError, ValueError):
            quantity = 1

        product = get_object_or_404(Products, id=product_id)
        if not size_id:
            default_size = Product_sizes.objects.filter(prod_id=product.id).first()
            if not default_size:
                default_size = Product_sizes.objects.create(
                    prod_id=product.id,
                    size="Standard",
                    price=999,
                    quantity=10,
                    status=1,
                    creation_date=date.today(),
                )
            size_id = default_size.id

        cart_item = Cart.objects.filter(
            customer_id=customer_id,
            product_id=product.id,
            size_id=size_id,
            status="pending",
        ).first()

        if cart_item:
            cart_item.quantity += quantity
            cart_item.save()
        else:
            Cart.objects.create(
                customer_id=customer_id,
                product_id=product.id,
                size_id=size_id,
                quantity=quantity,
                status="pending",
            )

        _, sub_total, shipping, total, cart_count = _cart_totals_payload(customer_id)
        if is_ajax:
            return JsonResponse({
                'ok': True,
                'message': f'Added "{product.prod_name}" to your cart.',
                'cart_count': cart_count,
                'sub_total': sub_total,
                'shipping': shipping,
                'total': total,
            })

        messages.success(request, f'Added "{product.prod_name}" to your cart.')
        return redirect('cart')

    cart_items, sub_total, shipping, total, cart_count = _cart_totals_payload(customer_id)
    context = {
        'sub_total': sub_total,
        'cart_items': cart_items,
        'shipping': shipping,
        'total': total,
        'cart_count': cart_count,
    }
    return render(request, 'web/shop-cart.html', context)


def update_cart(request, cart_id):
    """Real-time quantity update (+1 / -1 / exact) for a cart item."""
    if request.method != "POST":
        return redirect('cart')

    customer_id = _get_cart_customer_id(request)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    cart_item = get_object_or_404(Cart, id=cart_id, customer_id=customer_id, status="pending")

    action = request.POST.get('action')
    if action == 'inc':
        cart_item.quantity += 1
        cart_item.save()
    elif action == 'dec':
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
            cart_item = None
    elif request.POST.get('quantity') is not None:
        try:
            qty = int(request.POST.get('quantity'))
        except (TypeError, ValueError):
            qty = cart_item.quantity
        if qty <= 0:
            cart_item.delete()
            cart_item = None
        else:
            cart_item.quantity = qty
            cart_item.save()

    cart_items, sub_total, shipping, total, cart_count = _cart_totals_payload(customer_id)
    item_qty = cart_item.quantity if cart_item else 0
    item_subtotal = 0
    if cart_item:
        size_obj = Product_sizes.objects.filter(id=cart_item.size_id).first()
        item_subtotal = (size_obj.price or 0) * item_qty if size_obj else 0

    if is_ajax:
        return JsonResponse({
            'ok': True,
            'removed': cart_item is None,
            'item_qty': item_qty,
            'item_subtotal': item_subtotal,
            'sub_total': sub_total,
            'shipping': shipping,
            'total': total,
            'cart_count': cart_count,
        })
    return redirect('cart')


def delete_cart(request, cart_id):
    customer_id = _get_cart_customer_id(request)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    cart_item = get_object_or_404(Cart, id=cart_id, customer_id=customer_id)
    cart_item.delete()
    if is_ajax:
        _, sub_total, shipping, total, cart_count = _cart_totals_payload(customer_id)
        return JsonResponse({
            'ok': True,
            'sub_total': sub_total,
            'shipping': shipping,
            'total': total,
            'cart_count': cart_count,
        })
    messages.success(request, "Item removed from cart.")
    return redirect('cart')


def clear_cart(request):
    customer_id = _get_cart_customer_id(request)
    Cart.objects.filter(customer_id=customer_id, status='pending').delete()
    messages.success(request, "Cart cleared successfully.")
    return redirect('cart')


def fetch_cart_details(customer_id, status="pending"):
    query = """
        SELECT 
            main.id AS mid,
            main.quantity,
            '' AS customer_name,
            COALESCE(prod.prod_name, 'Handcrafted Item') AS prod_name,
            COALESCE(sizz.price, 0) AS price,
            COALESCE(sizz.size, 'Standard') AS size,
            main.product_id AS prodid,
            main.size_id,
            COALESCE(prod.image, '/static/web/img/product/product-1.jpg') AS image,
            (COALESCE(sizz.price, 0) * main.quantity) AS subtotal,
            (COALESCE(sizz.price, 0) * main.quantity + 100) AS total
        FROM tab_cart main
        LEFT JOIN tab_products prod ON main.product_id = prod.id
        LEFT JOIN tab_product_size sizz ON main.size_id = sizz.id
        WHERE main.customer_id = %s AND main.status = %s
        ORDER BY main.id DESC
    """
    with connection.cursor() as cursor:
        cursor.execute(query, [str(customer_id), status])
        rows = cursor.fetchall()
    return rows


def fetch_items_details(customer_id, status="pending"):
    query = """
       SELECT 
            main.id AS mid,
            main.quantity,
            '' AS customer_name,
            COALESCE(prod.prod_name, 'Handcrafted Item') AS prod_name,
            COALESCE(sizz.price, 0) AS price,
            COALESCE(sizz.size, 'Standard') AS size,
            main.product_id AS prodid,
            main.size_id,
            COALESCE(prod.image, '/static/web/img/product/product-1.jpg') AS image,
            (COALESCE(sizz.price, 0) * main.quantity) AS subtotal
        FROM tab_order_item main
        LEFT JOIN tab_order ord ON main."order" = ord.id
        LEFT JOIN tab_products prod ON main.product_id = prod.id
        LEFT JOIN tab_product_size sizz ON main.size_id = sizz.id
        WHERE ord.customer_id = %s AND main.status = %s
        ORDER BY main.id DESC
    """
    with connection.cursor() as cursor:
        cursor.execute(query, [str(customer_id), status])
        rows = cursor.fetchall()
    return rows

    

# def cart(request):
#     return render(request,"web/shop-cart.html")

def checkout(request):
    if not request.user.is_authenticated and not request.session.get('userid'):
        messages.info(request, 'Please sign in to complete your order.')
        return redirect(f"{reverse('login')}?next={reverse('checkout')}")
    customer_id = _get_cart_customer_id(request)

    today = timezone.now().date()
    cart_items = fetch_cart_details(customer_id)

    # Check if there's already a pending order
    existing_order = Order.objects.filter(status="pending", customer_id=customer_id).first()

    if not cart_items and not existing_order:
        if not existing_order:
            messages.error(request, 'Firstly choose Product then Confirm order')
            return redirect("cart")
        else:
            messages.info(request, 'Items already in pending order.')
            return redirect("cart")

    total_amount = 0
    cart_ids = []

    for item in cart_items:
        cart_id = item[0]  # main.id
        quantity = item[1]
        product_id = item[6]
        size_id = item[7]
        price = item[4]

        cart_ids.append(cart_id)

        if existing_order:
            # Check for existing order item in this order
            existing_item = OrderItem.objects.filter(
                order=existing_order.id,
                product_id=product_id,
                size_id=size_id,
                status="pending"
            ).first()

            if existing_item:
                # Update quantity
                existing_item.quantity += quantity
                existing_item.save()
            else:
                # Create new item in existing order
                OrderItem.objects.create(
                    order=existing_order.id,
                    product_id=product_id,
                    size_id=size_id,
                    offer_id=0,
                    quantity=quantity,
                    status="pending"
                )

            total_amount += price * quantity

        else:
            # No existing order: prepare to create one
            total_amount += price * quantity

    # If no existing order, create new one and add items
    if not existing_order:
        new_order = Order.objects.create(
            customer_id=customer_id,
            order_date=today,
            order_amount=total_amount,
            status="pending",
            delivery_partner_id=None,
        )
        request.session["order_id"] = new_order.id

        for item in cart_items:
            OrderItem.objects.create(
                order=new_order.id,
                product_id=item[6],
                size_id=item[7],
                offer_id=0,
                quantity=item[1],
                status="pending"
            )
    else:
        # Update existing order total amount
        existing_order.order_amount += total_amount
        existing_order.save()
        request.session["order_id"] = existing_order.id

    # Mark cart items as inprocess
    Cart.objects.filter(id__in=cart_ids).update(status="inprocess")
    order_items = fetch_items_details(customer_id=customer_id, status="pending")
    sub_total = sum(item[9] for item in order_items)  # assuming item[9] is the price
    shipping = 100  # Flat rate or your logic
    total = sub_total + shipping
    context = {
    'sub_total': sub_total,
    'order_items':order_items,
    'shipping': shipping,
    'total': total,
    }

    return render(request, 'web/checkout.html',context)



def submit_shipping(request):
    ordid = request.session.get('order_id')
    customer_id = _get_cart_customer_id(request)
    if request.method == "POST":
        payment_mode = request.POST.get('payment_mode', 'UPI')
        request.session['payment_mode'] = payment_mode

        ship = Shipment.objects.create(
            first_name=request.POST.get('first_name', ''),
            last_name=request.POST.get('last_name', ''),
            address=request.POST.get('address', ''),
            state=request.POST.get('state', ''),
            country=request.POST.get('country', 'India'),
            zip_code=request.POST.get('zip_code', ''),
            customer_id=customer_id or '',
            order_id=ordid,
            note=request.POST.get('note', ''),
            status=int(request.POST.get('status', 0)),
            creation_date=timezone.now(),
            mob_num=request.POST.get('mob_num', ''),
            town=request.POST.get('town', ''),
        )
        request.session["ship_user"] = ship.id
        Cart.objects.filter(status='inprocess', customer_id=customer_id).update(status="ordered")
        OrderItem.objects.filter(status='pending', order=ordid).update(status="inprocess")
        Order.objects.filter(status='pending', id=ordid).update(status="inprocess")
        return redirect('order_final')
    return redirect('checkout')


def order_final(request):
    if not request.user.is_authenticated and not request.session.get('userid'):
        messages.error(request, 'You need to login first to complete your order.')
        return redirect('login')
    customer_id = _get_cart_customer_id(request)

    ordid = request.session.get('order_id')
    if not ordid:
        messages.error(request, 'Order not found.')
        return redirect('checkout')

    try:
        order_obj = Order.objects.get(id=ordid)
    except Order.DoesNotExist:
        messages.error(request, 'Order not found.')
        return redirect('checkout')

    items = fetch_items_details(customer_id, status="inprocess")
    payment_mode = request.session.get('payment_mode', 'UPI')
    total_rupees = order_obj.order_amount + 100
    total_paisa = int(total_rupees * 100)
    request.session['order_amount'] = total_paisa

    razorpay_order_id = None
    if payment_mode == 'Card' and razorpay_client is not None:
        try:
            razorpay_order = razorpay_client.order.create(data={
                "amount": total_paisa,
                "currency": "INR",
                "receipt": f"rcpt_{uuid.uuid4().hex[:8]}",
                "payment_capture": 0,
            })
            razorpay_order_id = razorpay_order.get('id')
        except Exception:
            razorpay_order_id = None

    context = {
        'order_id': razorpay_order_id or f'AV-{order_obj.id}',
        'db_order_id': order_obj.id,
        'amount': total_paisa,
        'amount_rupees': total_rupees,
        'razorpay_key': settings.RAZOR_KEY_ID,
        'currency': 'INR',
        'payment_mode': payment_mode,
        'items': items,
        'customer_id': customer_id,
        'callback_url': request.build_absolute_uri(reverse('paymenthandler')),
    }
    return render(request, 'web/order_final.html', context)


def confirm_payment(request):
    """Confirm UPI, Net Banking, Card (demo/fallback), or Cash on Delivery orders."""
    if request.method != "POST":
        return redirect('order_final')

    order_id = request.session.get('order_id')
    customer_id = _get_cart_customer_id(request)
    amount_paisa = request.session.get('order_amount', 0)
    payment_mode = request.POST.get('payment_mode') or request.session.get('payment_mode', 'UPI')

    if order_id and customer_id:
        pay_status = "Pending COD" if payment_mode == "Cash on Delivery" else "Success"
        order_status = "inprocess" if payment_mode == "Cash on Delivery" else "paid"
        Payment.objects.create(
            order_id=str(order_id),
            customer_id=str(customer_id),
            payment_mode=payment_mode,
            amount=f"{amount_paisa / 100:.2f}",
            status=pay_status,
            creation_date=timezone.now().date(),
        )
        OrderItem.objects.filter(order=order_id, status="inprocess").update(status="ordered")
        Order.objects.filter(id=order_id).update(status=order_status)
        if request.session.get('ship_user'):
            Shipment.objects.filter(id=request.session.get('ship_user')).update(status=1)

    return render(request, 'web/thankyou.html', {'payment_mode': payment_mode})
@csrf_exempt
def paymenthandler(request):
    if request.method == "POST":
        try:
            # Extract Razorpay data from POST request
            payment_id = request.POST.get('razorpay_payment_id')
            razorpay_order_id = request.POST.get('razorpay_order_id')
            signature = request.POST.get('razorpay_signature')

            # Check if all necessary Razorpay data is present
            if not all([payment_id, razorpay_order_id, signature]):
                print("Missing payment data")
                return HttpResponseBadRequest("Missing payment data")

            # Verify signature
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }

            # Replace 'razorpay_client' with your actual Razorpay client object
            razorpay_client.utility.verify_payment_signature(params_dict)

            # If verification passes, render thank you page
            return redirect('thankyou')

        except razorpay.errors.SignatureVerificationError as e:
            print("Signature verification failed:", e)
            return redirect('failpage')

        except Exception as e:
            print("General Exception:", e)
            return HttpResponseBadRequest("Something went wrong.")
    else:
        return HttpResponse("Invalid request method", status=405)


def thankyou(request):
    try:
        order_id = request.session.get('order_id')
        customer_id = request.session.get('userid')
        user_email = request.session.get('useremail')
        amount = request.session.get('order_amount')

        if all([order_id, customer_id, user_email, amount]):
            # Save success payment
            Payment.objects.create(
                order_id=order_id,
                customer_id=customer_id,
                payment_mode="Online",
                amount=amount/100,
                status="Success",
                creation_date=timezone.now().date()
            )

            # Update order items to ordered
            OrderItem.objects.filter(order=order_id, status="inprocess").update(status="ordered")
            Order.objects.filter(id=order_id, status="inprocess").update(status="ordered")
            Shipment.objects.filter(id=request.session.get('ship_user')).update(status="ordered")
    except Exception as e:
        print("Error in thankyou:", e)

    return render(request, 'web/thankyou.html')

def user_orders(request):
    if not request.user.is_authenticated and not request.session.get('userid'):
        messages.error(request, "Please login to view your orders.")
        return redirect(f"{reverse('login')}?next={reverse('user_orders')}")
    customer_id = _get_cart_customer_id(request)

    orders = fetch_user_orders(customer_id)

    return render(request, 'web/orders.html', {'orders': orders})


def fetch_user_orders(customer_id):
    query = """
       SELECT 
    ord.id AS order_id,
    ord.order_date,
    ord.order_amount,
    ord.status,
    prod.prod_name,
    itm.quantity,
    size.price,
    size.size,
    prod.image
FROM tab_order ord
LEFT JOIN tab_order_item itm ON itm."order" = ord.id
LEFT JOIN tab_products prod ON itm.product_id = prod.id
LEFT JOIN tab_product_size size ON itm.size_id = size.id
WHERE ord.customer_id = %s
ORDER BY ord.id DESC
    """
    with connection.cursor() as cursor:
        cursor.execute(query, [str(customer_id)])
        rows = cursor.fetchall()

    # Group orders by order_id
    orders = {}
    for row in rows:
        order_id = row[0]
        order_date = row[1]
        order_amount = row[2]
        status = row[3]
        prod_name = row[4]
        quantity = row[5]
        price = row[6]
        size = row[7]
        image = row[8]

        if order_id not in orders:
            orders[order_id] = {
                'order_date': order_date,
                'order_amount': order_amount,
                'status': status,
                'items': []
            }

        orders[order_id]['items'].append({
            'product': prod_name,
            'quantity': quantity,
            'price': price,
            'size': size,
            'subtotal': price * quantity if price else 0,
            'image': image
        })

    return orders

def wishlist(request):
    return render(request,"web/wishlist.html")

def about(request):
    return render(request,"web/about.html")

def contact(request):
    return render(request,"web/contact.html")

def _get_safe_next_url(request, default_url='dashboard'):
    """Return a safe ?next= redirect target or the default route."""
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return default_url


def _authenticate_user(request, identifier, password):
    """Authenticate against Django's auth User by username or email."""
    user = authenticate(request, username=identifier, password=password)
    if user is None and '@' in identifier:
        matched_user = AuthUser.objects.filter(email__iexact=identifier).first()
        if matched_user:
            user = authenticate(request, username=matched_user.username, password=password)
    return user


def _handle_login(request, template_name):
    """Shared login handler for storefront login and panel signin."""
    next_url = request.GET.get('next') or request.POST.get('next', '')
    if request.user.is_authenticated:
        return redirect(_get_safe_next_url(request, 'dashboard'))

    form_errors = []
    entered_identifier = ''

    if request.method == 'POST':
        entered_identifier = (
            request.POST.get('username')
            or request.POST.get('email')
            or ''
        ).strip()
        password = request.POST.get('password') or request.POST.get('pass') or ''

        if not entered_identifier:
            form_errors.append('Please enter your username or email.')
        if not password:
            form_errors.append('Please enter your password.')

        if not form_errors:
            user = _authenticate_user(request, entered_identifier, password)
            if user is not None:
                if user.is_active:
                    guest_session_key = request.session.session_key
                    auth_login(request, user)
                    _merge_guest_cart(request, user, guest_session_key)
                    request.session['userid'] = user.id
                    request.session['username'] = user.get_full_name() or user.username
                    request.session['useremail'] = user.email
                    messages.success(request, f'Welcome back, {user.username}!')
                    return redirect(_get_safe_next_url(request, 'dashboard'))
                form_errors.append('Your account is inactive. Please contact support.')
            else:
                form_errors.append('Invalid username/email or password. Please try again.')

        for err in form_errors:
            messages.error(request, err)

    return render(
        request,
        template_name,
        {
            'next': next_url,
            'entered_identifier': entered_identifier,
            'form_errors': form_errors,
        },
    )


def login_view(request):
    return _handle_login(request, 'web/login.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form_errors = []
    form_data = {'username': '', 'email': '', 'mobile': ''}

    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        email = (request.POST.get('email') or '').strip()
        mobile = (request.POST.get('mobile') or '').strip()
        password = request.POST.get('password') or ''
        confirm_password = request.POST.get('confirm_password') or ''

        form_data = {'username': username, 'email': email, 'mobile': mobile}

        if not username:
            form_errors.append('Username is required.')
        elif AuthUser.objects.filter(username__iexact=username).exists():
            form_errors.append('That username is already taken.')

        if not email:
            form_errors.append('Email address is required.')
        elif AuthUser.objects.filter(email__iexact=email).exists():
            form_errors.append('An account with this email already exists.')

        if not password:
            form_errors.append('Password is required.')
        elif password != confirm_password:
            form_errors.append('Passwords do not match.')
        else:
            try:
                validate_password(password)
            except ValidationError as exc:
                form_errors.extend(exc.messages)

        if not form_errors:
            auth_user = AuthUser.objects.create_user(
                username=username,
                email=email,
                password=password,
            )
            if mobile and mobile.isdigit():
                User.objects.get_or_create(
                    email=email,
                    defaults={
                        'name': username,
                        'mobile': int(mobile),
                        'password': '',
                        'status': 1,
                        'created_on': date.today(),
                    },
                )
            auth_login(request, auth_user)
            request.session['userid'] = auth_user.id
            request.session['username'] = auth_user.username
            request.session['useremail'] = auth_user.email
            messages.success(request, 'Account created successfully! Welcome to Artisans-Verse.')
            return redirect('dashboard')

        for err in form_errors:
            messages.error(request, err)

    return render(
        request,
        'web/register.html',
        {'form_errors': form_errors, 'form_data': form_data},
    )


def logout_view(request):
    auth_logout(request)
    messages.info(request, 'You have been signed out.')
    return redirect('login')


def userlogout(request):
    return logout_view(request)


def password_reset(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        if not email:
            messages.error(request, "Please enter your email address.")
            return redirect("login")

        user = AuthUser.objects.filter(email__iexact=email).first()
        if not user:
            messages.error(request, "No account found with that email address.")
            return redirect("login")

        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        user.set_password(new_password)
        user.save()

        send_mail(
            subject="Artisans-Verse Password Reset",
            message=f"Hello {user.username},\n\nYour temporary password is: {new_password}\nPlease change your password after logging in.",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
            fail_silently=True,
        )
        messages.success(request, "A temporary password has been sent to your email.")
        return redirect("login")

    return redirect("login")


@login_required
def dashboard(request):
    products_qs = Products.objects.all().order_by('-id')
    categories_qs = Category.objects.all()
    brands_qs = Brands.objects.all()
    offers_qs = Offers.objects.all()
    orders_qs = Order.objects.all().order_by('-id')
    sizes_qs = Product_sizes.objects.all()

    category_map = {c.id: c.cat_name for c in categories_qs}
    brand_map = {b.id: b.name for b in brands_qs}

    recent_products = []
    for prod in products_qs[:8]:
        prod_sizes = sizes_qs.filter(prod_id=prod.id)
        first_size = prod_sizes.first()
        total_stock = prod_sizes.aggregate(total=Sum('quantity'))['total'] or 0
        recent_products.append({
            'id': prod.id,
            'name': prod.prod_name,
            'category': category_map.get(prod.parent_cat, 'Handcrafted'),
            'brand': brand_map.get(prod.brand, 'Local Artisan'),
            'price': first_size.price if first_size and first_size.price is not None else 0,
            'stock': total_stock,
            'status': prod.status,
            'image': prod.image,
            'created': prod.creation_date,
        })

    low_stock_items = []
    product_name_map = {p.id: p.prod_name for p in products_qs}
    for sz in sizes_qs.filter(quantity__lte=5).order_by('quantity')[:6]:
        low_stock_items.append({
            'prod_id': sz.prod_id,
            'prod_name': product_name_map.get(sz.prod_id, f'Product #{sz.prod_id}'),
            'size': sz.size,
            'quantity': sz.quantity or 0,
            'price': sz.price or 0,
        })

    total_revenue = orders_qs.aggregate(total=Sum('order_amount'))['total'] or 0
    pending_orders_count = orders_qs.filter(status__in=['pending', 'inprocess']).count()
    total_inventory_units = sizes_qs.aggregate(total=Sum('quantity'))['total'] or 0

    total_prod_count = max(products_qs.count(), 1)
    category_stats = []
    for cat in categories_qs[:6]:
        count = products_qs.filter(parent_cat=cat.id).count()
        category_stats.append({
            'name': cat.cat_name,
            'count': count,
            'pct': round((count / total_prod_count) * 100),
        })

    recent_payments = Payment.objects.all().order_by('-id')[:6]

    context = {
        'username': request.user.get_full_name() or request.user.username,
        'usermail': request.user.email or 'artisan@artisans-verse.local',
        'total_products': products_qs.count(),
        'active_products': products_qs.filter(status=1).count(),
        'total_categories': categories_qs.count(),
        'total_brands': brands_qs.count(),
        'active_offers': offers_qs.filter(status=1).count(),
        'total_orders': orders_qs.count(),
        'pending_orders_count': pending_orders_count,
        'total_revenue': total_revenue,
        'total_inventory_units': total_inventory_units,
        'recent_products': recent_products,
        'recent_orders': orders_qs[:6],
        'low_stock_items': low_stock_items,
        'brands_list': brands_qs[:6],
        'category_stats': category_stats,
        'recent_payments': recent_payments,
    }
    return render(request, 'panel/index.html', context)


def forgot_password(request):
    return password_reset(request)


def signin(request):
    return _handle_login(request, 'panel/signin.html')

def show_nav(request):
    parent_categories = Category.objects.filter(parent_cat__isnull=True, sub_cat__isnull=True)
    subcategories = Category.objects.filter(parent_cat__isnull=False, sub_cat__isnull=True)
    sub_subcategories = Category.objects.filter(parent_cat__isnull=False, sub_cat__isnull=False)

    menu_items = []

    for parent in parent_categories:
        parent_subcategories = subcategories.filter(parent_cat=parent.id)

        subcategory_items = []
        for subcategory in parent_subcategories:
            sub_subcategory_items = sub_subcategories.filter(parent_cat=parent.id, sub_cat=subcategory.id)

            subcategory_items.append({
                'subcategory': {
                    'id': subcategory.id,
                    'name': subcategory.cat_name,
                },
                'sub_subcategories': [
                    {
                        'id': sub.id,
                        'name': sub.cat_name
                    } for sub in sub_subcategory_items
                ]
            })

        menu_items.append({
            'parent': {
                'id': parent.id,
                'name': parent.cat_name,
            },
            'subcategories': subcategory_items
        })

    return JsonResponse({'menu_items': menu_items},safe=True)


def logout(request):
    return logout_view(request)


#Fetch Data by using query
def fetch_data(query):
    """Execute any SQL query and return fetched results."""
    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()

def category(request):
    data={}
    query ="SELECT main.id as mid, main.cat_name, main.describ as cat_description,parent.cat_name as parent_cat, sub.cat_name as sub_cat,main.image, main.status FROM tab_category as main LEFT JOIN tab_category as parent ON main.parent_cat = parent.id LEFT JOIN tab_category as sub ON main.sub_cat = sub.id"
    # with connection.cursor() as cursor:
    #     cursor.execute(query)
    #     result = cursor.fetchall()
    #     
        
    if request.method=="POST":
        if request.FILES.get('myfile'):
            myfile = request.FILES['myfile']
            
            # Define the custom static storage path
            static_upload_folder = os.path.join(settings.BASE_DIR, 'artistapp/static/uploads/')
            os.makedirs(static_upload_folder, exist_ok=True)  # Ensure directory exists
            
            # Save file to static/upload/
            fs = FileSystemStorage(location=static_upload_folder)
            filename = fs.get_available_name(myfile.name)  # Ensures unique filename
            saved_filename = fs.save(filename, myfile)
            
            # URL to access the uploaded file
            uploaded_file_url = f"/static/uploads/{saved_filename}"
        else:
            uploaded_file_url = "/static/uploads/default.jpeg"
        catname=request.POST["catname"]
        describe=request.POST["catDescription"]
        parent = int(request.POST["catParent"]) if request.POST["catParent"] != '0' else None
        sub = int(request.POST["subCategory"]) if request.POST["subCategory"] != '0' else None
        status=request.POST["catAvailability"]
        cdate=date.today()
        addCat=Category(
            cat_name=catname,
            parent_cat=parent,
            sub_cat=sub,
            describ=describe,
            status=status,
            image=uploaded_file_url,
            creation_date=cdate
        )
        addCat.save()
        if addCat:
            data["msgs"]="Category Created well done"
            data["category"]=fetch_data(query)
            return render(request,"panel/category.html",data)
    data["msgs"]=""
    data["category"]=fetch_data(query)
    return render(request,"panel/category.html",data)

def parentCategory(request):
    getParents = Category.objects.filter(parent_cat__isnull=True)  # Get all parent categories
    data = list(getParents.values('id', 'cat_name'))  # Convert QuerySet to a list of dictionaries
    return JsonResponse(data, safe=False)  # Return JSON response   

def subCategory(request):
    if request.method == "GET" and request.GET.get("val") :  # Corrected request.GET
        parent_id = request.GET.get("val")  # Get the parent category ID from AJAX request
        getSubcat = Category.objects.filter(parent_cat=parent_id,sub_cat=None)  # Filter by parent category

        data = list(getSubcat.values('id', 'cat_name'))  # Convert QuerySet to list of dictionaries
        return JsonResponse(data, safe=False)  # Return JSON response

    return JsonResponse({"error": "Invalid request"}, status=400)  # Handle invalid requests


def subsubCategory(request):
    if request.method == "GET" and request.GET.get("val") and request.GET.get("get") :  # Corrected request.GET
        parent_id = request.GET.get("val")  # Get the parent category ID from AJAX request
        sub_id = request.GET.get("get")  # Get the parent category ID from AJAX request
        getSubcat = Category.objects.filter(parent_cat=parent_id, sub_cat=sub_id)  # Filter by parent category

        data = list(getSubcat.values('id', 'cat_name'))  # Convert QuerySet to list of dictionaries
        return JsonResponse(data, safe=False)  # Return JSON response

    return JsonResponse({"error": "Invalid request"}, status=400)  # Handle invalid requests


#Update Category
def category_edit(request, id):
    data = {}
    category = get_object_or_404(Category, id=id)
    if request.method == "POST":
        if request.FILES.get('myfile'):
            myfile = request.FILES['myfile']
            
            # Define the custom static storage path
            static_upload_folder = os.path.join(settings.BASE_DIR, 'artistapp/static/uploads/')
            os.makedirs(static_upload_folder, exist_ok=True)  # Ensure directory exists
            
            # Save file to static/upload/
            fs = FileSystemStorage(location=static_upload_folder)
            filename = fs.get_available_name(myfile.name)  # Ensures unique filename
            saved_filename = fs.save(filename, myfile)
            
            # URL to access the uploaded file
            uploaded_file_url = f"/static/uploads/{saved_filename}"
            category.cat_image = uploaded_file_url
        else:
            uploaded_file_url = request.POST["hidimage"]
        
        category.cat_name = request.POST['catname']
        category.describ = request.POST['catDescription']
        category.parent_cat = int(request.POST['catParent']) if request.POST['catParent'] != '0' else None
        category.sub_cat = int(request.POST['subCategory']) if request.POST['subCategory'] != '0' else None
        category.status = bool(int(request.POST['catAvailability']))
        category.image=uploaded_file_url
        category.save()
        # data['msgs'] = category
        messages.success(request, 'Category Updated Successfully!')
        return redirect('category')

    data['cat'] = category
    return render(request, 'panel/category_edit.html', data)


#Delete Category
def category_delete(request, id):
    category = get_object_or_404(Category, id=id)
    category.delete()
    messages.success(request, 'Category Deleted Successfully!')
    return redirect('category')


#Brands
def brands(request):
    data={}
    if request.method=="POST":
        if request.FILES.get('myfile'):
            myfile = request.FILES['myfile']
            
            # Define the custom static storage path
            static_upload_folder = os.path.join(settings.BASE_DIR, 'artistapp/static/uploads/')
            os.makedirs(static_upload_folder, exist_ok=True)  # Ensure directory exists
            
            # Save file to static/upload/
            fs = FileSystemStorage(location=static_upload_folder)
            filename = fs.get_available_name(myfile.name)  # Ensures unique filename
            saved_filename = fs.save(filename, myfile)
            
            # URL to access the uploaded file
            uploaded_file_url = f"/static/uploads/{saved_filename}"
        else:
            uploaded_file_url = "/static/uploads/default.jpeg"
        brand_name=request.POST["brand_name"]
        brand_desc=request.POST["brand_desc"]
        since =  request.POST["since"]
        status=request.POST["catAvailability"]
        cdate=date.today()
        addBrand=Brands(
            name=brand_name,
            since=since,
            describ=brand_desc,
            status=status,
            image=uploaded_file_url,
            creation_date=cdate
        )
        addBrand.save()
        if addBrand:
            data["msgs"]="Brand Created Successfully"
            data["brands"] = Brands.objects.all()
            return render(request,"panel/brands.html",data)
    data["msgs"]=""
    data["brands"] = Brands.objects.all()
    return render(request,"panel/brands.html",data)


def brand_edit(request, id):
    data = {}
    brand = get_object_or_404(Brands, id=id)
    if request.method == "POST":
        if request.FILES.get('myfile'):
            myfile = request.FILES['myfile']
            
            # Define the custom static storage path
            static_upload_folder = os.path.join(settings.BASE_DIR, 'artistapp/static/uploads/')
            os.makedirs(static_upload_folder, exist_ok=True)  # Ensure directory exists
            
            # Save file to static/upload/
            fs = FileSystemStorage(location=static_upload_folder)
            filename = fs.get_available_name(myfile.name)  # Ensures unique filename
            saved_filename = fs.save(filename, myfile)
            
            # URL to access the uploaded file
            uploaded_file_url = f"/static/uploads/{saved_filename}"
            brand.cat_image = uploaded_file_url
        else:
            uploaded_file_url = request.POST["hidimage"]
        
        brand.name = request.POST['brand_name']
        brand.describ = request.POST['brand_desc']
        brand.since =request.POST['since']
        brand.status = bool(int(request.POST['catAvailability']))
        brand.image=uploaded_file_url
        brand.save()
        # data['msgs'] = category
        messages.success(request, 'Brand Updated Successfully!')
        return redirect('brands')

    data['brand'] = brand
    return render(request, 'panel/brand_edit.html', data)

def brand_delete(request, id):
    brands = get_object_or_404(Brands, id=id)
    brands.delete()
    messages.success(request, 'Brands Deleted Successfully!')
    return redirect('brands')

def get_brands(request):
    getBrands = Brands.objects.all()  # Get all parent categories
    data = list(getBrands.values('id', 'name'))  # Convert QuerySet to a list of dictionaries
    return JsonResponse(data, safe=False)

#Offers

def offers(request):
    data={}
    if request.method=="POST":
        if request.FILES.get('myfile'):
            myfile = request.FILES['myfile']
            
            # Define the custom static storage path
            static_upload_folder = os.path.join(settings.BASE_DIR, 'artistapp/static/uploads/')
            os.makedirs(static_upload_folder, exist_ok=True)  # Ensure directory exists
            
            # Save file to static/upload/
            fs = FileSystemStorage(location=static_upload_folder)
            filename = fs.get_available_name(myfile.name)  # Ensures unique filename
            saved_filename = fs.save(filename, myfile)
            
            # URL to access the uploaded file
            uploaded_file_url = f"/static/uploads/{saved_filename}"
        else:
            uploaded_file_url = "/static/uploads/default.jpeg"
        offer_title=request.POST["offer_title"]
        offer_describ=request.POST["offer_describ"]
        offer_code=request.POST["offer_code"]
        sdate=request.POST["sdate"]
        edate=request.POST["edate"]
        status=request.POST["catAvailability"]
        cdate=date.today()
        addOffers=Offers(
            title=offer_title,
            describ=offer_describ,
            offer_code=offer_code,
            start_date=sdate,
            end_date=edate,
            status=status,
            image=uploaded_file_url,
            creation_date=cdate
        )
        addOffers.save()
        if addOffers:
            data["msgs"]="offer Created Successfully"
            data["offers"] = Offers.objects.all()
            return render(request,"panel/offers.html",data)
    data["msgs"]=""
    data["offers"] = Offers.objects.all()
    return render(request,"panel/offers.html",data)


def offer_edit(request, id):
    data = {}
    offers = get_object_or_404(Offers, id=id)
    if request.method == "POST":
        if request.FILES.get('myfile'):
            myfile = request.FILES['myfile']
            
            # Define the custom static storage path
            static_upload_folder = os.path.join(settings.BASE_DIR, 'artistapp/static/uploads/')
            os.makedirs(static_upload_folder, exist_ok=True)  # Ensure directory exists
            
            # Save file to static/upload/
            fs = FileSystemStorage(location=static_upload_folder)
            filename = fs.get_available_name(myfile.name)  # Ensures unique filename
            saved_filename = fs.save(filename, myfile)
            
            # URL to access the uploaded file
            uploaded_file_url = f"/static/uploads/{saved_filename}"
            offers.cat_image = uploaded_file_url
        else:
            uploaded_file_url = request.POST["hidimage"]
        
        offers.title = request.POST['offer_title']
        offers.offer_code = request.POST['offer_code']
        offers.describ = request.POST['offer_describ']
        offers.start_date =request.POST['sdate']
        offers.end_date =request.POST['edate']
        offers.status = bool(int(request.POST['catAvailability']))
        offers.image=uploaded_file_url
        offers.save()
        # data['msgs'] = category
        messages.success(request, 'Offers Updated Successfully!')
        return redirect('offers')

    data['offers'] = offers
    return render(request, 'panel/offer_edit.html', data)

def offer_delete(request, id):
    offers = get_object_or_404(Offers, id=id)
    offers.delete()
    messages.success(request, 'Offers Deleted Successfully!')
    return redirect('offers')


def products(request):
    data = {}
    query = """SELECT main.id as mid,
    main.prod_name, 
    parent.cat_name as parent,
    sub.cat_name as sub, 
    subsub.cat_name as subsub, 
    main.describ, main.image 
               FROM tab_products main 
               LEFT JOIN tab_category parent ON main.parent_cat = parent.id 
               LEFT JOIN tab_category sub ON main.sub_cat = sub.id 
               LEFT JOIN tab_category subsub ON main.sub_sub_cat = subsub.id"""

    if request.method == "POST":
        # Handle Image Upload
        if request.FILES.get('myfile'):
            myfile = request.FILES['myfile']
            static_upload_folder = os.path.join(settings.BASE_DIR, 'artistapp/static/uploads/')
            os.makedirs(static_upload_folder, exist_ok=True)  # Ensure directory exists
            fs = FileSystemStorage(location=static_upload_folder)
            filename = fs.get_available_name(myfile.name)  # Ensures unique filename
            saved_filename = fs.save(filename, myfile)
            uploaded_file_url = f"/static/uploads/{saved_filename}"
            image_type = myfile.content_type.split("/")[-1]  # Extract file type (jpg, png, etc.)
            image_size = myfile.size  # Get file size in bytes
        else:
            uploaded_file_url = "/static/uploads/default.jpeg"
            image_type = "jpeg"  # Extract file type (jpg, png, etc.)
            image_size = 50  # Get file size in bytes

        # Get product details from the form
        prod_name = request.POST["prod_name"]
        brand = request.POST["brand"]
        describ = request.POST["describe"]
        parent = int(request.POST["catParent"]) if request.POST["catParent"] != '0' else None
        sub = int(request.POST["subCategory"]) if request.POST["subCategory"] != '0' else None
        sub_sub = int(request.POST["subsubCategory"]) if request.POST["subsubCategory"] != '0' else None
        status = request.POST["catAvailability"]
        cdate = date.today()

        # Step 1: Insert into `tab_products`
        new_product = Products(
            prod_name=prod_name,
            brand=brand,
            parent_cat=parent,
            sub_cat=sub,
            sub_sub_cat=sub_sub,
            describ=describ,
            status=status,
            image=uploaded_file_url,
            creation_date=cdate
        )
        new_product.save()

        # Step 2: Insert into `tab_product_images`
        product_image = Product_images(
            prod_id=new_product.id,
            size=image_size,  # Store image size in bytes
            image_type=image_type,
            path=uploaded_file_url,
            status=1,
            creation_date=cdate # Save the image path
        )
        product_image.save()

        # Step 3: Insert into `tab_product_sizes`
        sizes = request.POST["size"]  # Array of sizes from the form
        quantities = request.POST["stock"]  # Array of quantities
        prices = request.POST["price"] # Array of prices

        product_size = Product_sizes(
            prod_id=new_product.id,
            size=sizes,
            quantity=quantities,
            price=prices,
            status=1,
            creation_date=cdate
        )
        product_size.save()

        data["msgs"] = "Product Created Successfully!"
        data["products"] = fetch_data(query)
        return render(request, "panel/product.html", data)

    data["msgs"] = ""
    data["products"] = fetch_data(query)
    return render(request, "panel/product.html", data)


#Update Category
def product_edit(request, id):
    data = {}
    product = get_object_or_404(Products, id=id)  # Fetch product instead of category

    if request.method == "POST":
        if request.FILES.get('myfile'):
            myfile = request.FILES['myfile']

            # Define the custom static storage path
            static_upload_folder = os.path.join(settings.BASE_DIR, 'artistapp/static/uploads/')
            os.makedirs(static_upload_folder, exist_ok=True)  # Ensure directory exists

            # Save file to static/upload/
            fs = FileSystemStorage(location=static_upload_folder)
            filename = fs.get_available_name(myfile.name)  # Ensures unique filename
            saved_filename = fs.save(filename, myfile)

            # URL to access the uploaded file
            uploaded_file_url = f"/static/uploads/{saved_filename}"
            product.image = uploaded_file_url
        else:
            uploaded_file_url = request.POST.get("hidimage", product.image)

        # Update product fields
    
        product.prod_name = request.POST['prod_name']
        product.brand = request.POST['brand']
        product.describ = request.POST['describe']
        product.status = request.POST['catAvailability']
        product.parent_cat = int(request.POST["catParent"]) if request.POST["catParent"] != '0' else None
        product.sub_cat = int(request.POST["subCategory"]) if request.POST["subCategory"] != '0' else None
        product.sub_sub_cat = int(request.POST["subsubCategory"]) if request.POST["subsubCategory"] != '0' else None
        product.image = uploaded_file_url
        product.save()

        messages.success(request, 'Product Updated Successfully!')
        return redirect('products')  # Redirect to product list page

    # Pass only product data to the template
    data['product'] = product
    return render(request, 'panel/product_edit.html', data)

#Delete Category
def product_delete(request, id):
    Product = get_object_or_404(Products, id=id)
    Product.delete()
    messages.success(request, 'Products Deleted Successfully!')
    return redirect('products')

#Product Size CRUD
def product_sizes(request, prod_id):
    """Display product details along with sizes related to the product and allow adding new sizes."""
    
    # Get the product details
    product = get_object_or_404(Products, id=prod_id)  

    # Get all sizes related to the product
    sizes = Product_sizes.objects.filter(prod_id=product.id)

    if request.method == "POST":
        size_value = request.POST.get("size")  # Get size input from form
        price = request.POST.get("price")  # Get price input from form
        stock = request.POST.get("stock")  # Get stock input from form
        prodid = request.POST.get("prodid")  # Get stock input from form
        status = request.POST.get("catAvailability")  # Get stock input from form
        cdate = date.today()
        # Create a new size entry
        new_size = Product_sizes.objects.create(
            prod_id=prodid, 
            size=size_value, 
            price=price, 
            quantity=stock,
            status=status,
            creation_date=cdate
        )

        # Redirect to the same page to avoid form resubmission issues
        return render(request,"panel/product_sizes.html", {
        "product": product.prod_name,  
        "prod_id": product.id,  
        "sizes": sizes,  
    })

    return render(request, "panel/product_sizes.html", {
        "product": product.prod_name,  
        "prod_id": product.id,  
        "sizes": sizes,  
    })


def update_product_size(request, prod_id, size_id):
    """Update product size for a given product"""
    product = get_object_or_404(Products, id=prod_id)
    size_instance = get_object_or_404(Product_sizes, id=size_id, prod_id=prod_id)  # Ensure it belongs to the same product

    if request.method == "POST":
        size_instance.size = request.POST.get("size")
        size_instance.quantity = request.POST.get("stock")
        size_instance.price = request.POST.get("price")
        size_instance.status = request.POST.get("catAvailability")
        size_instance.save()
        return redirect(f"/product_sizes/{prod_id}/")  # Redirect back to sizes list

    return render(request, "panel/size_edit.html", {
        "product": product.prod_name,  
        "prod_id": product.id, 
        "size": size_instance
    })
 


def size_delete(request, prod_id,size_id):
    Sizes = get_object_or_404(Product_sizes, id=size_id)
    Sizes.delete()
    messages.success(request, 'Product Size Deleted Successfully!')
    return redirect(f"/product_sizes/{prod_id}/")    

#Product Image Crud

def product_images(request, prod_id):
    """Display and upload product images"""
    
    product = get_object_or_404(Products, id=prod_id)
    images = Product_images.objects.filter(prod_id=product.id)

    if request.method == "POST" and request.FILES.get("myfile"):
        myfile = request.FILES['myfile']

        # Define the custom static storage path
        static_upload_folder = os.path.join(settings.BASE_DIR, 'artistapp/static/uploads/')
        os.makedirs(static_upload_folder, exist_ok=True)  # Ensure directory exists

        # Save file to static/upload/
        fs = FileSystemStorage(location=static_upload_folder)
        filename = fs.get_available_name(myfile.name)  # Ensures unique filename
        saved_filename = fs.save(filename, myfile)

        # URL to access the uploaded file
        uploaded_file_url = f"/static/uploads/{saved_filename}"
        image_type = myfile.content_type.split("/")[-1]  # Extract file type (jpg, png, etc.)
        image_size = myfile.size
        # Save to database
        cdate = date.today()

        product_image = Product_images.objects.create(
            prod_id=product.id,
            size=image_size,
            image_type=image_type,
            path=uploaded_file_url,
            status=1,
            creation_date=cdate
        )
        product_image.save()
    
    return render(request, "panel/product_image.html", {
        "product": product.prod_name,
        "prod_id": product.id,
        "images": images,
    })

def update_product_image(request, prod_id, image_id):
    """Update product image and remove old image"""
    
    product = get_object_or_404(Products, id=prod_id)
    image_instance = get_object_or_404(Product_images, id=image_id, prod_id=prod_id)

    if request.method == "POST" and request.FILES.get("myfile"):
        myfile = request.FILES["myfile"]

        #  Define the custom static storage path
        static_upload_folder = os.path.join(settings.BASE_DIR, 'artistapp/static/uploads/')
        os.makedirs(static_upload_folder, exist_ok=True)  # Ensure directory exists

        #  Delete the old image from storage
        old_image_path = os.path.join(settings.BASE_DIR, "artistapp" + image_instance.path)
        if os.path.exists(old_image_path):
            os.remove(old_image_path)

        #  Save new file to static/uploads/
        fs = FileSystemStorage(location=static_upload_folder)
        filename = fs.get_available_name(myfile.name)  # Ensure unique filename
        saved_filename = fs.save(filename, myfile)

        #  URL to access the uploaded file
        uploaded_file_url = f"/static/uploads/{saved_filename}"
        image_type = myfile.content_type.split("/")[-1]  # Extract file type (jpg, png, etc.)
        image_size = myfile.size

        #  Update database entry
        image_instance.size = image_size
        image_instance.image_type = image_type
        image_instance.path = uploaded_file_url
        image_instance.status=1
        image_instance.save()

        return redirect(f"/product_images/{prod_id}/")  # Redirect to images list

    return render(request, "panel/update_image.html", {
        "product": product.prod_name,  
        "prod_id": product.id, 
        "image": image_instance
    })

def delete_product_image(request, prod_id, image_id):
    """Delete a product image"""
    
    image_instance = get_object_or_404(Product_images, id=image_id, prod_id=prod_id)
    
    # Delete from storage
    if image_instance.path:
        image_path = os.path.join(settings.MEDIA_ROOT, str(image_instance.path))
        if os.path.exists(image_path):
            os.remove(image_path)

    # Delete from database
    image_instance.delete()
    
    return redirect(f"/product_images/{prod_id}/")    