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
    code = models.CharField(max_length=50, unique=True)
    discount = models.DecimalField(max_digits=5, decimal_places=2)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.discount}%"

