from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index,name='index'),
    # path('details/', views.shop_detail,name='shop_detail'),
    path('shop/', views.shop,name='shop'),
    path('shop/<int:parent>/<int:sub>/<int:subsub>/', views.shop, name="shop"),
    path('shop_detail/<int:prod_id>/', views.shop_detail,name="shop_detail"),
    path('get-size-details/<int:size_id>/', views.get_size_details, name='get_size_details'),
    path('delete_cart//<int:cart_id>/', views.delete_cart,name="delete_cart"),
    path('clear-cart/', views.clear_cart, name='clear_cart'),
    path('cart/', views.cart,name='cart'),
    path('checkout/', views.checkout,name='checkout'),
    path('submit_shipping/', views.submit_shipping,name="submit_shipping"),
    path('order_final/', views.order_final,name="order_final"),
    path('thankyou/', views.thankyou,name="thankyou"),
    path('paymenthandler/', views.paymenthandler, name='paymenthandler'),
    path('user_orders/', views.user_orders, name='user_orders'),
    path('wishlist/', views.wishlist,name='wishlist'),
    path('about/', views.about,name='about'),
    path('contact/', views.contact,name='contact'),
    path('register/', views.register,name="register"),
    path('login/', views.login,name="login"),
    path('userlogout/', views.userlogout,name="userlogout"),
    path('password_reset/', views.password_reset,name="password_reset"),
    path('shownav/', views.show_nav,name="shownav"),
    
     #Admin based routes
    path('dashboard/', views.dashboard,name='dashboard'),
    path('signin/', views.signin,name="signin"),
    path('logout/', views.logout,name="logout"),
    path('forgot_pass/', views.forgot_password,name="forgot_pass"),

    path('category/', views.category, name="category"),
    path('category_edit/<int:id>/', views.category_edit, name="category_edit"),
    path('category_delete/<int:id>/', views.category_delete, name="category_delete"),
    path('get-parent/', views.parentCategory, name="parentcat"),
    path('get-subs/', views.subCategory, name="sub_cat"),
    path('sub_sub_cat/', views.subsubCategory, name="sub_sub_cat"),
    
    #Brands
    path('brands/', views.brands, name="brands"),
    path('get-brands/', views.get_brands, name="get-brands"),
    path('brand_edit/<int:id>/', views.brand_edit, name="brand_edit"),
    path('brand_delete/<int:id>/', views.brand_delete, name="brand_delete"),
    
    #Offers
    path('offers/', views.offers, name="offers"),
    path('offer_edit/<int:id>/', views.offer_edit, name="offer_edit"),
    path('offer_delete/<int:id>/', views.offer_delete, name="offer_delete"),
    
    #Products
    path('products/', views.products, name="products"),
    path('product_edit/<int:id>/', views.product_edit, name="product_edit"),
    path('product_delete/<int:id>/', views.product_delete, name="product_delete"),
    
    #Product_images
    path("product_sizes/<int:prod_id>/", views.product_sizes, name="product_sizes"),
    path('size_edit/<int:prod_id>/<int:size_id>/', views.update_product_size,name='size_edit'),
    path('size_delete/<int:prod_id>/<int:size_id>/', views.size_delete,name='size_delete'),
    
    #Product_images
    path("product_images/<int:prod_id>/", views.product_images, name="product_images"),
    path('image_edit/<int:prod_id>/<int:image_id>/', views.update_product_image,name='image_edit'),
]
