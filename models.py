from django.db import models

# Create your models here.
class User(models.Model):
    id=models.AutoField(primary_key=True)
    name=models.CharField(max_length=100)
    mobile=models.BigIntegerField()
    email=models.CharField(max_length=100,unique=True)
    password=models.CharField(max_length=100)
    status=models.SmallIntegerField()
    created_on=models.DateField()
    
    class Meta:
         # Prevents Django from running migrations
        db_table="user"
        
class Admin(models.Model):
    id=models.AutoField(primary_key=True)
    name=models.CharField(max_length=100)
    email=models.CharField(max_length=100)
    password=models.CharField(max_length=100)
    status=models.SmallIntegerField()
    created_on=models.DateField()
    
    class Meta:
         # Prevents Django from running migrations
        db_table="admin"        

class Category(models.Model):
    id=models.AutoField(primary_key=True)
    cat_name=models.CharField(max_length=100)
    parent_cat = models.IntegerField(null=True, blank=True) 
    sub_cat=models.IntegerField(null=True, blank=True)
    image=models.CharField(max_length=200)
    status=models.IntegerField()
    describ=models.TextField(blank=True, default="No description available")
    creation_date=models.DateField()
    
    class Meta:
         # Prevents Django from running migrations
        db_table="tab_category"        


class Brands(models.Model):
    id=models.AutoField(primary_key=True)
    name=models.CharField(max_length=100)
    describ=models.TextField(blank=True, default="No description available")
    since = models.IntegerField(null=True, blank=True,default=2025) 
    image=models.CharField(max_length=200)
    status=models.IntegerField()
    creation_date=models.DateField()
    
    class Meta:
         # Prevents Django from running migrations
        db_table="tab_brand"            
        

class Offers(models.Model):
    id=models.AutoField(primary_key=True)
    title=models.CharField(max_length=100)
    offer_code=models.CharField(max_length=100,default="AddXYZ")
    describ=models.TextField(blank=True, default="No description available")
    start_date=models.DateField()
    discount=models.IntegerField(default=0)
    end_date=models.DateField()
    image=models.CharField(max_length=200)
    status=models.IntegerField()
    creation_date=models.DateField()
    
    class Meta:
         # Prevents Django from running migrations
        db_table="tab_offers" 
        

class Products(models.Model):
    id=models.AutoField(primary_key=True)
    prod_name=models.CharField(max_length=100)
    brand=models.IntegerField(null=True, blank=True) 
    parent_cat = models.IntegerField(null=True, blank=True) 
    sub_cat=models.IntegerField(null=True, blank=True)
    sub_sub_cat=models.IntegerField(null=True, blank=True)
    image=models.CharField(max_length=200)
    status=models.IntegerField()
    describ=models.TextField(blank=True, default="No description available")
    creation_date=models.DateField()
    
    class Meta:
         # Prevents Django from running migrations
        db_table="tab_products"
        
class Product_sizes(models.Model):
    id=models.AutoField(primary_key=True)
    prod_id=models.IntegerField(null=False, blank=True)
    size = models.CharField(max_length=50,default="xs") 
    price=models.IntegerField(null=True, blank=True)
    quantity=models.IntegerField(null=True, blank=True)
    describ=models.TextField(blank=True, default="No description available")
    status=models.IntegerField()
    creation_date=models.DateField()
    
    class Meta:
         # Prevents Django from running migrations
        db_table="tab_product_size"                      
        
class Product_images(models.Model):
    id=models.AutoField(primary_key=True)
    prod_id=models.IntegerField(null=False, blank=True)
    size = models.CharField(max_length=100,default="xs") 
    image_type=models.CharField(max_length=100,default="jpeg")
    path=models.TextField(blank=True)
    status=models.IntegerField()
    creation_date=models.DateField()
    
    class Meta:
         # Prevents Django from running migrations
        db_table="tab_product_images"      
        

class Cart(models.Model):
    customer_id = models.CharField(max_length=255)  # Can be email or user ID
    product_id = models.IntegerField()
    size_id = models.IntegerField()  # Added size_id as per your request
    quantity = models.IntegerField(default=1)
    status = models.CharField(max_length=20, choices=[("ordered", "Ordered"), ("pending", "Pending"),("inprocess","Inprocess")], default="pending")
    creation_dt = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed=False
        db_table="tab_cart"
        
    def __str__(self):
        return f"Cart {self.id} - {self.customer_id}"                                
    
class Order(models.Model):
    STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('inprocess', 'In Process'),
    ]

    customer_id = models.CharField(max_length=255)  # Assuming it's an email, change to ForeignKey if needed
    order_date = models.DateField()
    order_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    creation_date = models.DateField(auto_now_add=True)
    delivery_partner_id = models.IntegerField(null=True, blank=True)  # Nullable if delivery partner is not assigned

    class Meta:
        db_table="tab_order"
        
    def __str__(self):
        return f"Order {self.id} - {self.customer_id}"
    
    

class OrderItem(models.Model):
    order = models.BigIntegerField()
    product_id = models.IntegerField()
    size_id = models.IntegerField()
    offer_id = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2,default=100)
    quantity = models.IntegerField()
    status = models.CharField(max_length=20, default='pending')  # Adjust if you want choices
    creation_date = models.DateField(auto_now_add=True)

    class Meta:
        db_table="tab_order_item"
        
    def __str__(self):
        return f"OrderItem {self.id} - Order {self.order.id}"   
    

class Shipment(models.Model):
    STATUS_CHOICES = [
        (0, 'Pending'),
        (1, 'Shipped'),
        (2, 'Delivered'),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    order_id=models.IntegerField(null=True)
    address = models.TextField()
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    customer_id = models.EmailField()
    note = models.TextField(null=True, blank=True)
    payment_id = models.IntegerField(null=True, blank=True)
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)
    creation_date = models.DateTimeField()
    mob_num = models.CharField(max_length=20)
    town = models.CharField(max_length=100)
    
    class Meta:
        db_table="tab_shipment"
        
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.customer_id}"         
    
    
class Payment(models.Model):
    order_id = models.CharField(max_length=500)
    customer_id = models.CharField(max_length=500)
    payment_mode = models.CharField(max_length=500)
    amount = models.CharField(max_length=500)
    status = models.CharField(max_length=500)
    creation_date = models.DateField()

    class Meta:
        db_table = "tab_payment"

    def __str__(self):
        return self.order_id