from datetime import timedelta
from django.db import models
from django.conf import settings
from django.utils import timezone
# Create your models here.

class PasswordResetOTP(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)

    otp_hash = models.CharField(max_length=128)

    created_at = models.DateTimeField(auto_now=True)

    expires_at = models.DateTimeField()

    attempts = models.PositiveSmallIntegerField(default=0)

    verified = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"Password reset OTP for {self.user.username}"

class Categories(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Subcategories(models.Model):
    category = models.ForeignKey(Categories, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Colors(models.Model):
    name=models.CharField(max_length=100)
    def __str__(self):
        return self.name
class Sizes(models.Model):
    name=models.CharField(max_length=50)
    def __str__(self):
        return self.name

class Product(models.Model):
    subcategory=models.ForeignKey(Subcategories,on_delete=models.CASCADE)
    color=models.ForeignKey(Colors,on_delete=models.CASCADE,blank=True,null=True)
    size=models.ForeignKey(Sizes,on_delete=models.CASCADE,blank=True,null=True)
    name=models.CharField(max_length=200)
    price=models.DecimalField(max_digits=10,decimal_places=2)
    image=models.ImageField(upload_to='products/',blank=True,null=True)
    stock = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return self.name

class CartItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def total_price(self):
        return self.product.price * self.quantity

    def __str__(self):
        return self.product.name

class Coupons(models.Model):
    DURATION_CHOICES = [
        ('custom', 'Custom (use End Date)'),
        ('12h', '12 Hours'),
        ('1d', '1 Day'),
        ('2d', '2 Days'),
        ('3d', '3 Days'),
        ('7d', '7 Days'),
        ('30d', '30 Days'),
    ]

    code = models.CharField(max_length=50, unique=True)
    discount = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )
    active = models.BooleanField(default=True)
    duration = models.CharField(
        max_length=20,
        choices=DURATION_CHOICES,
        default='custom',
        blank=True
    )
    start_date = models.DateTimeField(
        default=timezone.now
    )
    end_date = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.start_date:
            self.start_date = timezone.now()
        if self.duration == '12h':
            self.end_date = self.start_date + timedelta(hours=12)
        elif self.duration == '1d':
            self.end_date = self.start_date + timedelta(days=1)
        elif self.duration == '2d':
            self.end_date = self.start_date + timedelta(days=2)
        elif self.duration == '3d':
            self.end_date = self.start_date + timedelta(days=3)
        elif self.duration == '7d':
            self.end_date = self.start_date + timedelta(days=7)
        elif self.duration == '30d':
            self.end_date = self.start_date + timedelta(days=30)
        super().save(*args, **kwargs)

    def is_valid(self):
        now = timezone.now()
        return (
            self.active
            and self.start_date <= now
            and (not self.end_date or now < self.end_date)
            and 0 < self.discount <= 100
        )

    def is_expired(self):
        if not self.active:
            return True
        if self.end_date and timezone.now() >= self.end_date:
            return True
        return False

    def time_remaining_display(self):
        if not self.end_date:
            return "No expiry"
        now = timezone.now()
        if now >= self.end_date:
            return "Expired"
        diff = self.end_date - now
        hours = int(diff.total_seconds() // 3600)
        minutes = int((diff.total_seconds() % 3600) // 60)
        if diff.days > 0:
            return f"{diff.days}d {hours % 24}h remaining"
        elif hours > 0:
            return f"{hours}h {minutes}m remaining"
        else:
            return f"{minutes}m remaining"

    def __str__(self):
        return f"{self.code} - {self.discount}%"


class ShopCarousel(models.Model):
    ITEM_TYPES = [
        ('discount', 'Discount Item'),
        ('new', 'New Item'),
    ]

    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True, null=True)
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES, default='discount')
    badge_text = models.CharField(max_length=100, blank=True, null=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    image = models.ImageField(upload_to='shop_carousel/', blank=True, null=True)
    link = models.CharField(max_length=255, default='#')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-id']

    def __str__(self):
        return f"{self.title} ({self.get_item_type_display()})"


class BillingAddress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    mobile_no = models.CharField(max_length=20)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=100, default='United States')
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Billing Addresses'

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.city}, {self.country}"


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    billing_address = models.ForeignKey(BillingAddress, on_delete=models.CASCADE)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    shipping = models.DecimalField(max_digits=10, decimal_places=2, default=60.00)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, default='Direct Check')
    is_paid = models.BooleanField(default=False)
    order_status = models.CharField(
        max_length=50,
        choices=[
            ('Pending', 'Pending'),
            ('Processing', 'Processing'),
            ('Shipped', 'Shipped'),
            ('Delivered', 'Delivered'),
            ('Cancelled', 'Cancelled'),
        ],
        default='Pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} by {self.billing_address.first_name} (₹{self.total_amount})"


