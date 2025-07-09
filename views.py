import os
import uuid
from django.db import connection
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from .models import Cart, Order, OrderItem, Payment, Shipment, User,Admin,Category,Brands,Offers,Product_images,Products,Product_sizes
import base64,random,string
from datetime import date
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from local_art import settings
import razorpay
from django.views.decorators.csrf import csrf_exempt

razorpay_client = razorpay.Client(
    auth=(settings.RAZOR_KEY_ID, settings.RAZOR_KEY_SECRET))

def index(request):
    if request.session.get('userid'):
        return render(request,"web/index.html",{"username":request.session.get('username'),"usermail":request.session.get('useremail')})
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
    
    categorys = Category.objects.filter(parent_cat__isnull=True, sub_cat__isnull=True)
    return render(request,"web/index.html")

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
    
def cart(request):
    customer_id = request.session.get('userid')
    if not customer_id:
        messages.error(request, 'You need to login first to see your cart')
        return redirect('login')  # Or wherever your login page is

    if request.method == "POST":
        product_id = request.POST.get('prodid')
        size_id = request.POST.get('sizeid')
        quantity = int(request.POST.get('quantity', 1))

        # Check if the same product-size combo already exists in pending cart
        cart_item = Cart.objects.filter(
            customer_id=customer_id,
            product_id=product_id,
            size_id=size_id,
            status="pending"  # Pending
        ).first()

        if cart_item:
            cart_item.quantity += quantity
            cart_item.save()
        else:
            Cart.objects.create(
                customer_id=customer_id,
                product_id=product_id,
                size_id=size_id,
                quantity=quantity,
                status="pending",  # Pending
                creation_dt=date.today()
            )

        return redirect('cart')  # Go back to cart page after adding/updating

    # GET request: Show cart items
    cart_items = fetch_cart_details(customer_id=customer_id, status="pending")
    sub_total = sum(item[9] for item in cart_items)  # assuming item[9] is the price
    shipping = 100  # Flat rate or your logic
    total = sub_total + shipping
    context = {
    'sub_total': sub_total,
    'cart_items':cart_items,
    'shipping': shipping,
    'total': total,
    }
    return render(request, 'web/shop-cart.html', context)


def delete_cart(request, cart_id):
    customer_id = request.session.get('userid')
    if not customer_id:
        messages.error(request, "You must be logged in to modify your cart.")
        return redirect('login')

    cart_item = get_object_or_404(Cart, id=cart_id, customer_id=customer_id)
    cart_item.delete()
    messages.success(request, "Item removed from cart.")
    return redirect('cart')  # Redirect back to cart page

def clear_cart(request):
    customer_id = request.session.get('userid')
    if not customer_id:
        messages.error(request, "You must be logged in to modify your cart.")
        return redirect('login')

    Cart.objects.filter(customer_id=customer_id, status='pending').delete()
    messages.success(request, "Cart cleared successfully.")
    return redirect('cart')

def fetch_cart_details(customer_id, status="pending"):
    query = """
        SELECT 
            main.id AS mid,
            main.quantity,
            usez.name,
            prod.prod_name,
            sizz.price,
            sizz.size,
            main.product_id as prodid,
            main.size_id,
            prod.image,
            (sizz.price *  main.quantity) AS subtotal,
            (sizz.price *  main.quantity +100) AS total
        FROM tab_cart main
        LEFT JOIN user usez ON main.customer_id = usez.id
        LEFT JOIN tab_products prod ON main.product_id = prod.id
        LEFT JOIN tab_product_size sizz ON main.size_id = sizz.id
        WHERE main.customer_id = %s AND main.status = %s
    """
    with connection.cursor() as cursor:
        cursor.execute(query, [customer_id, status])
        rows = cursor.fetchall()
    return rows

def fetch_items_details(customer_id, status="pending"):
    query = """
       SELECT 
            main.id AS mid,
            main.quantity,
            usez.name,
            prod.prod_name,
            sizz.price,
            sizz.size,
            main.product_id as prodid,
            main.size_id,
            prod.image,
            (sizz.price *  main.quantity) AS subtotal
        FROM tab_order_item main
        LEFT JOIN tab_order ord on main.order=ord.id
        LEFT JOIN user usez ON ord.customer_id = usez.id
        LEFT JOIN tab_products prod ON main.product_id = prod.id
        LEFT JOIN tab_product_size sizz ON main.size_id = sizz.id
        WHERE ord.customer_id = %s AND main.status = %s
    """
    with connection.cursor() as cursor:
        cursor.execute(query, [customer_id, status])
        rows = cursor.fetchall()
    return rows

    

# def cart(request):
#     return render(request,"web/shop-cart.html")

def checkout(request):
    customer_id = request.session.get('userid')
    if not customer_id:
        messages.error(request, 'You need to login first to see your cart')
        return redirect('login')

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
    if request.session.get('order_id'):
        ordid=request.session.get('order_id')
    customer_id = request.session.get('userid')    
    if request.method == "POST":
        ship=Shipment.objects.create(
            first_name = request.POST.get('first_name'),
            last_name = request.POST.get('last_name'),
            address = request.POST.get('address'),
            state = request.POST.get('state'),
            country = request.POST.get('country'),
            zip_code = request.POST.get('zip_code'),
            customer_id = customer_id,
            order_id=ordid,
            note = request.POST.get('note'),
            status = int(request.POST.get('status', 0)),  # default to 0 if not sent
            creation_date = timezone.now(),
            mob_num = request.POST.get('mob_num'),
            town = request.POST.get('town')
        )
        request.session["ship_user"]=ship.id
        Cart.objects.filter(status='inprocess',customer_id=customer_id).update(status="ordered")
        OrderItem.objects.filter(status='pending',order=ordid).update(status="inprocess")
        Order.objects.filter(status='pending',id=ordid).update(status="inprocess")
        return redirect('order_final')  # show a confirmation page

def order_final(request):
    # Check if user is logged in
    customer_id = request.session.get('userid')
    if not customer_id:
        messages.error(request, 'You need to login first to see your cart')
        return redirect('login')

    # Get order ID from session
    ordid = request.session.get('order_id')
    if not ordid:
        messages.error(request, 'Order not found.')
        return redirect('checkout')

    # Get the order from DB
    try:
        order_obj = Order.objects.get(id=ordid)
    except Order.DoesNotExist:
        messages.error(request, 'Order not found.')
        return redirect('checkout')

    # Fetch cart items
    items = fetch_items_details(customer_id, status="inprocess")

    # Razorpay amount must be in paisa
    total = (order_obj.order_amount + 100) * 100  # Rs -> paisa
    request.session['order_amount'] = int(total)  # In paisa
    print("Amount:",total)
    # Create Razorpay order
    client = razorpay.Client(auth=(settings.RAZOR_KEY_ID, settings.RAZOR_KEY_SECRET))
    DATA = {
        "amount": int(total),
        "currency": "INR",
        "receipt": f"rcpt_{uuid.uuid4().hex[:8]}",  # Unique receipt ID
        "payment_capture": 0  # manual capture
    }

    try:
        razorpay_order = client.order.create(data=DATA)
    except Exception as e:
        print("Razorpay Error:", e)
        messages.error(request, "Failed to initiate payment. Please try again.")
        return redirect('checkout')

    # Build callback URL
    callback_url = request.build_absolute_uri(reverse('paymenthandler'))

    # Send details to template
    context = {
        'order_id': razorpay_order['id'],
        'amount': int(total),
        'razorpay_key': settings.RAZOR_KEY_ID,
        'currency': DATA['currency'],
        'items': items,
        'customer_id': customer_id,
        'callback_url': callback_url
    }

    print("Razorpay Order Payload:", DATA)
    return render(request, 'web/order_final.html', context)
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
    customer_id = request.session.get('userid')
    if not customer_id:
        messages.error(request, "Please login to view your orders.")
        return redirect('login')  # or wherever your login route is

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
LEFT JOIN tab_order_item itm ON itm.order = ord.id
LEFT JOIN tab_products prod ON itm.product_id = prod.id
LEFT JOIN tab_product_size size ON itm.size_id = size.id
WHERE ord.customer_id = %s
ORDER BY ord.id DESC
    """
    with connection.cursor() as cursor:
        cursor.execute(query, [customer_id])
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

def login(request):
    if request.method == "POST":
        username = request.POST['email']
        password = request.POST['pass']
        encpass = base64.b64encode(password.encode('utf-8')).decode("utf-8")

        try:
            getuser = User.objects.get(email=username, password=encpass)
            request.session["userid"] = getuser.id
            request.session["username"] = getuser.name
            request.session["useremail"] = getuser.email
            return redirect("index")
        except User.DoesNotExist:
            messages.error(request, "Invalid email or password")  # Display error message

    return render(request, "web/login.html")

def register(request):
    if request.method=="POST":
        name=request.POST["username"]  
        mobile=request.POST["mobile"]  
        email=request.POST["email"]  
        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        encrypted_password = base64.b64encode(new_password.encode("utf-8")).decode("utf-8")
        modobj=User(
            name=name,
            status=1,
            email=email,
            mobile=mobile,
            password=encrypted_password,
            created_on=date.today()
        )
        modobj.save()
        if(modobj):
            send_mail(
            subject="Your New Password",
            message=f"Hello {name},\n\nYour Requested Password is: {new_password}\nYou can change your password anytime after logging in.",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
            )
            return render(request,"web/register.html",{"msg":"User Register Successfully"})
    return render(request,'web/register.html')

def userlogout(request):
    request.session.flush()
    return redirect("/")

def password_reset(request):
    if request.method == "POST":
        email = request.POST["email"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return render(request, "web/signin.html", {"msgs": "Email not found. Please try again."})

        # Generate a temporary random password
        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        encrypted_password = base64.b64encode(new_password.encode("utf-8")).decode("utf-8")

        # Save the encrypted password in the database
        user.password = encrypted_password
        user.save()

        # Send email with the new password
        send_mail(
            subject="Your New Password",
            message=f"Hello {user.name},\n\nYour new password is: {new_password}\nPlease change your password after logging in.",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
        )

        return render(request, "web/signin.html", {"msgs": "A new password has been sent to your email."})

    return render(request, "web/signin.html")


# def signin(request):
#     return render(request,"web/signin.html")

# def signup(request):
#     return render(request,"web/signup.html")



def dashboard(request):
    if request.session.get('adminid'):
        return render(request,'panel/index.html',{"username":request.session.get('adminname'),"usermail":request.session.get('adminemail')})
    return render(request,"panel/index.html")

def forgot_password(request):
    if request.method == "POST":
        email = request.POST["email"]

        try:
            user = Admin.objects.get(email=email)
        except Admin.DoesNotExist:
            return render(request, "panel/index.html", {"msgs": "Email not found. Please try again."})

        # Generate a temporary random password
        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        encrypted_password = base64.b64encode(new_password.encode("utf-8")).decode("utf-8")

        # Save the encrypted password in the database
        user.password = encrypted_password
        user.save()

        # Send email with the new password
        send_mail(
            subject="Your New Password",
            message=f"Hello {user.name},\n\nYour new password is: {new_password}\nPlease change your password after logging in.",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
        )

        return render(request, "panel/index.html", {"msgs": "A new password has been sent to your email."})

    return render(request, "panel/index.html")

#Admin Sign in
def signin(request):
    if request.method=="POST":
        username=request.POST['email']
        password=request.POST['pass']
        encpass=base64.b64encode(password.encode('utf-8')).decode("utf-8")
        getuser=Admin.objects.get(email=username,password=encpass)
        if getuser:
            request.session["adminid"]=getuser.id
            request.session["adminname"]=getuser.name
            request.session["adminemail"]=getuser.email
            return redirect("dashboard")

    return render(request,"panel/signin.html")

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
    request.session.flush()
    return redirect("/")


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