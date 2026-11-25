from django.contrib import admin
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

admin.site.register(User)
admin.site.register(Admin)
admin.site.register(Category)
admin.site.register(Brands)
admin.site.register(Offers)
admin.site.register(Products)
admin.site.register(Product_sizes)
admin.site.register(Product_images)
admin.site.register(Cart)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(Shipment)
admin.site.register(Payment)
