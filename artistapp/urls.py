from django.urls import path
from . import views

urlpatterns = [
    # Storefront & public pages
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('shop/', views.shop, name='shop'),
    path('shop/<int:parent>/', views.shop, name='shop_parent'),
    path('shop/<int:parent>/<int:sub>/', views.shop, name='shop_sub'),
    path('shop/<int:parent>/<int:sub>/<int:subsub>/', views.shop, name='shop_subsub'),
    path('shop_detail/<int:prod_id>/', views.shop_detail, name='shop_detail'),
    path('get_size_details/<int:size_id>/', views.get_size_details, name='get_size_details'),
    path('show_nav/', views.show_nav, name='show_nav'),
    path('wishlist/', views.wishlist, name='wishlist'),

    # Cart & Checkout
    path('cart/', views.cart, name='cart'),
    path('cart/update/<int:cart_id>/', views.update_cart, name='update_cart'),
    path('delete_cart/<int:cart_id>/', views.delete_cart, name='delete_cart'),
    path('clear_cart/', views.clear_cart, name='clear_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('submit_shipping/', views.submit_shipping, name='submit_shipping'),
    path('order_final/', views.order_final, name='order_final'),
    path('confirm_payment/', views.confirm_payment, name='confirm_payment'),
    path('paymenthandler/', views.paymenthandler, name='paymenthandler'),
    path('thankyou/', views.thankyou, name='thankyou'),
    path('user_orders/', views.user_orders, name='user_orders'),

    # Authentication (Django auth)
    path('login/', views.login_view, name='login'),
    path('signin/', views.signin, name='signin'),
    path('register/', views.register, name='register'),
    path('signup/', views.register, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('userlogout/', views.userlogout, name='userlogout'),
    path('password_reset/', views.password_reset, name='password_reset'),
    path('forgot_password/', views.forgot_password, name='forgot_password'),

    # Dashboard & Artisan Management Panel
    path('dashboard/', views.dashboard, name='dashboard'),
    path('category/', views.category, name='category'),
    path('parentcat/', views.parentCategory, name='parentcat'),
    path('sub_cat/', views.subCategory, name='sub_cat'),
    path('sub_sub_cat/', views.subsubCategory, name='sub_sub_cat'),
    path('category_edit/<int:id>/', views.category_edit, name='category_edit'),
    path('category_delete/<int:id>/', views.category_delete, name='category_delete'),

    path('brands/', views.brands, name='brands'),
    path('brand_edit/<int:id>/', views.brand_edit, name='brand_edit'),
    path('brand_delete/<int:id>/', views.brand_delete, name='brand_delete'),
    path('get-brands/', views.get_brands, name='get-brands'),

    path('offers/', views.offers, name='offers'),
    path('offer_edit/<int:id>/', views.offer_edit, name='offer_edit'),
    path('offer_delete/<int:id>/', views.offer_delete, name='offer_delete'),

    path('products/', views.products, name='products'),
    path('product_edit/<int:id>/', views.product_edit, name='product_edit'),
    path('product_delete/<int:id>/', views.product_delete, name='product_delete'),

    path('product_sizes/<int:prod_id>/', views.product_sizes, name='product_sizes'),
    path('size_edit/<int:prod_id>/<int:size_id>/', views.update_product_size, name='size_edit'),
    path('size_delete/<int:prod_id>/<int:size_id>/', views.size_delete, name='size_delete'),

    path('product_images/<int:prod_id>/', views.product_images, name='product_images'),
    path('image_edit/<int:prod_id>/<int:image_id>/', views.update_product_image, name='image_edit'),
    path('delete_product_image/<int:prod_id>/<int:image_id>/', views.delete_product_image, name='delete_product_image'),
]
