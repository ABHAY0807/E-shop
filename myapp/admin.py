from django.contrib import admin
from .models import Categories, Colors, Coupons, Sizes, Subcategories,Product

# Register your models here.
admin.site.register(Categories)
admin.site.register(Subcategories)
admin.site.register(Product)
admin.site.register(Colors)
admin.site.register(Sizes)
admin.site.register(Coupons)

