from datetime import date
from decimal import Decimal
from django.contrib.auth.models import User as AuthUser
from django.core.management.base import BaseCommand
from artistapp.models import Brands, Category, Order, Payment, Product_sizes, Products


class Command(BaseCommand):
    help = "Seed a demo artisan user and a rich handcrafted catalog for local development."

    def handle(self, *args, **options):
        user, created = AuthUser.objects.get_or_create(
            username="artisan_admin",
            defaults={
                "email": "admin@artisans-verse.local",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            user.set_password("Artisan@123")
            user.save()
            self.stdout.write(self.style.SUCCESS("Created demo superuser: artisan_admin / Artisan@123"))

        today = date.today()

        categories_spec = [
            ("Handcrafted Pottery", "/static/web/img/categories/category-1.jpg", "Wheel-thrown stoneware and terracotta vessels."),
            ("Handloom Textiles", "/static/web/img/categories/category-2.jpg", "Naturally dyed weaves and artisanal throws."),
            ("Carved Woodwork", "/static/web/img/categories/category-3.jpg", "Hand-chiseled teakwood trays, bowls, and decor."),
            ("Brass & Metalcraft", "/static/web/img/categories/category-4.jpg", "Forged brass lamps, incense holders, and tableware."),
        ]
        cats = {}
        for name, img, desc in categories_spec:
            cat, _ = Category.objects.get_or_create(
                cat_name=name,
                defaults={"image": img, "status": 1, "describ": desc, "creation_date": today},
            )
            cats[name] = cat

        brands_spec = [
            ("Mitti Craft Collective", "Rural studio crafting lead-free terracotta tableware.", 2018, "/static/web/img/product/product-1.jpg"),
            ("Kora Loom Studio", "Small-batch handloom weavers from Rajasthan.", 2020, "/static/web/img/product/product-2.jpg"),
            ("Deodar Woodcraft", "Sustainable Himalayan timber carving workshop.", 2016, "/static/web/img/product/product-3.jpg"),
            ("Kansa Heritage Guild", "Traditional sand-cast bronze and brass artisans.", 2015, "/static/web/img/product/product-4.jpg"),
        ]
        brands = {}
        for name, desc, since, img in brands_spec:
            b, _ = Brands.objects.get_or_create(
                name=name,
                defaults={"describ": desc, "since": since, "image": img, "status": 1, "creation_date": today},
            )
            brands[name] = b

        products_spec = [
            ("Terracotta Chai Kulhad Set", "Mitti Craft Collective", "Handcrafted Pottery", "/static/web/img/product/product-1.jpg", "Set of 6 hand-thrown clay cups fired in a wood kiln.", "Set of 6", 650, 18),
            ("Indigo Block-Print Stole", "Kora Loom Studio", "Handloom Textiles", "/static/web/img/product/product-2.jpg", "Hand-block printed organic cotton stole with natural indigo.", "Free Size", 1250, 4),
            ("Stoneware Pour-Over Carafe", "Mitti Craft Collective", "Handcrafted Pottery", "/static/web/img/product/product-3.jpg", "Matte speckled ceramic coffee carafe with matching dripper.", "600 ml", 1850, 12),
            ("Hand-Loomed Raw Silk Cushion", "Kora Loom Studio", "Handloom Textiles", "/static/web/img/product/product-4.jpg", "Textured tussar silk cushion cover with subtle zari border.", "16x16 in", 980, 22),
            ("Carved Teakwood Serving Platter", "Deodar Woodcraft", "Carved Woodwork", "/static/web/img/product/product-5.jpg", "Single-plank seasoned teak platter finished with beeswax.", "14 inch", 2100, 9),
            ("Walnut Spice Box (Masala Dabba)", "Deodar Woodcraft", "Carved Woodwork", "/static/web/img/product/product-6.jpg", "Seven-compartment hand-turned walnut spice organizer.", "Standard", 2450, 3),
            ("Hammered Kansa Thali Set", "Kansa Heritage Guild", "Brass & Metalcraft", "/static/web/img/product/product-7.jpg", "Hand-beaten pure bronze dining plate with two katoris.", "3-Piece", 3200, 7),
            ("Sand-Cast Brass Diya Pair", "Kansa Heritage Guild", "Brass & Metalcraft", "/static/web/img/product/product-8.jpg", "Traditional lotus-engraved oil lamps cast in solid brass.", "Pair", 1400, 15),
        ]

        added_count = 0
        for pname, bname, cname, img, desc, size_label, price, qty in products_spec:
            if not Products.objects.filter(prod_name=pname).exists():
                prod = Products.objects.create(
                    prod_name=pname,
                    brand=brands[bname].id,
                    parent_cat=cats[cname].id,
                    image=img,
                    status=1,
                    describ=desc,
                    creation_date=today,
                )
                Product_sizes.objects.create(
                    prod_id=prod.id,
                    size=size_label,
                    price=price,
                    quantity=qty,
                    status=1,
                    creation_date=today,
                )
                added_count += 1

        if not Order.objects.exists():
            o1 = Order.objects.create(customer_id="ananya@example.com", order_date=today, order_amount=Decimal("1900.00"), status="paid")
            o2 = Order.objects.create(customer_id="rohan@example.com", order_date=today, order_amount=Decimal("3200.00"), status="inprocess")
            o3 = Order.objects.create(customer_id="meera@example.com", order_date=today, order_amount=Decimal("2450.00"), status="pending")
            Payment.objects.create(order_id=str(o1.id), customer_id="ananya@example.com", payment_mode="UPI", amount="1900.00", status="Success", creation_date=today)
            Payment.objects.create(order_id=str(o2.id), customer_id="rohan@example.com", payment_mode="Card", amount="3200.00", status="Success", creation_date=today)
            Payment.objects.create(order_id=str(o3.id), customer_id="meera@example.com", payment_mode="Cash on Delivery", amount="2450.00", status="Pending COD", creation_date=today)

        self.stdout.write(self.style.SUCCESS(f"Seed complete. Added {added_count} new handcrafted product(s)."))
