from datetime import date
from django.contrib.auth.models import User as AuthUser
from django.test import TestCase
from django.urls import reverse
from artistapp.models import Cart, Order, Payment, Product_sizes, Products


class AuthDashboardFlowTests(TestCase):
    def setUp(self):
        self.user = AuthUser.objects.create_user(
            username="artisan_test",
            email="artisan@example.com",
            password="StrongPassword123!",
        )
        self.product = Products.objects.create(
            prod_name="Terracotta Test Vase",
            image="/static/web/img/product/product-1.jpg",
            status=1,
            describ="Hand-thrown clay vase.",
            creation_date=date.today(),
        )
        self.size = Product_sizes.objects.create(
            prod_id=self.product.id,
            size="Medium",
            price=850,
            quantity=10,
            status=1,
            creation_date=date.today(),
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/?next=/dashboard/", response.url)

    def test_invalid_login_shows_error(self):
        response = self.client.post(
            reverse("login"),
            {"username": "artisan_test", "password": "wrong-password"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username/email or password")

    def test_valid_login_redirects_to_dashboard_and_respects_next(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "artisan@example.com",
                "password": "StrongPassword123!",
                "next": reverse("dashboard"),
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Artisans-Verse Dashboard")
        self.assertContains(response, "artisan_test")

    def test_logout_redirects_and_protects_dashboard(self):
        self.client.force_login(self.user)
        logout_response = self.client.get(reverse("logout"))
        self.assertEqual(logout_response.status_code, 302)
        self.assertEqual(logout_response.url, reverse("login"))

        dash_response = self.client.get(reverse("dashboard"))
        self.assertEqual(dash_response.status_code, 302)
        self.assertIn("/login/?next=/dashboard/", dash_response.url)

    def test_public_storefront_pages_load(self):
        for url_name in ("index", "shop", "cart", "login", "signin", "register", "about", "contact"):
            resp = self.client.get(reverse(url_name))
            self.assertEqual(resp.status_code, 200, f"Failed for {url_name}")

    def test_realtime_ajax_cart_update_and_checkout_order_flow(self):
        # 1. Guest adds to cart via AJAX without explicit sizeid
        add_resp = self.client.post(
            reverse("cart"),
            {"prodid": self.product.id, "quantity": 1},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(add_resp.status_code, 200)
        data = add_resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["cart_count"], 1)
        self.assertEqual(data["sub_total"], 850)

        # 2. Increment quantity in real time
        cart_item = Cart.objects.first()
        inc_resp = self.client.post(
            reverse("update_cart", args=[cart_item.id]),
            {"action": "inc"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(inc_resp.status_code, 200)
        inc_data = inc_resp.json()
        self.assertEqual(inc_data["item_qty"], 2)
        self.assertEqual(inc_data["sub_total"], 1700)
        self.assertEqual(inc_data["total"], 1800)

        # 3. Sign in and merge guest cart -> checkout -> confirm UPI payment
        self.client.post(
            reverse("login"),
            {"username": "artisan_test", "password": "StrongPassword123!"},
        )
        checkout_resp = self.client.get(reverse("checkout"))
        self.assertEqual(checkout_resp.status_code, 200)
        self.assertContains(checkout_resp, "Terracotta Test Vase")

        ship_resp = self.client.post(
            reverse("submit_shipping"),
            {
                "first_name": "Aarav",
                "last_name": "Sharma",
                "address": "12 Craft Lane",
                "town": "Jaipur",
                "state": "Rajasthan",
                "zip_code": "302001",
                "country": "India",
                "mob_num": "9876543210",
                "payment_mode": "UPI",
            },
            follow=True,
        )
        self.assertEqual(ship_resp.status_code, 200)
        self.assertContains(ship_resp, "Complete Your Payment")

        pay_resp = self.client.post(
            reverse("confirm_payment"),
            {"payment_mode": "UPI"},
        )
        self.assertEqual(pay_resp.status_code, 200)
        self.assertContains(pay_resp, "Thank You for Supporting Local Artisans")
        self.assertEqual(Order.objects.filter(customer_id=str(self.user.id), status="paid").count(), 1)
        self.assertEqual(Payment.objects.filter(payment_mode="UPI", status="Success").count(), 1)

        orders_resp = self.client.get(reverse("user_orders"))
        self.assertEqual(orders_resp.status_code, 200)
        self.assertContains(orders_resp, "Terracotta Test Vase")
