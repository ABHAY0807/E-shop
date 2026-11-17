from django.contrib import admin
from .models import (
    Categories, Colors, Coupons, Sizes, Subcategories, Product,
    ShopCarousel, BillingAddress, Order
)

# Register your models here.
admin.site.register(Categories)
admin.site.register(Subcategories)
admin.site.register(Product)
admin.site.register(Colors)
admin.site.register(Sizes)

@admin.register(Coupons)
class CouponsAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'discount',
        'duration',
        'active',
        'start_date',
        'end_date',
        'is_valid_status',
    )

    list_filter = ('active', 'duration')
    search_fields = ('code',)

    fields = (
        'code',
        'discount',
        'duration',
        'active',
        'start_date',
        'end_date',
    )

    def is_valid_status(self, obj):
        return obj.is_valid()
    is_valid_status.boolean = True
    is_valid_status.short_description = "Valid Now"


@admin.register(ShopCarousel)
class ShopCarouselAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'item_type',
        'badge_text',
        'is_active',
        'order',
        'created_at',
    )
    list_filter = ('item_type', 'is_active')
    search_fields = ('title', 'subtitle')
    list_editable = ('is_active', 'order')


@admin.register(BillingAddress)
class BillingAddressAdmin(admin.ModelAdmin):
    list_display = (
        'first_name',
        'last_name',
        'email',
        'mobile_no',
        'city',
        'state',
        'country',
        'created_at',
    )
    search_fields = ('first_name', 'last_name', 'email', 'mobile_no', 'city')
    list_filter = ('country', 'state')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'billing_address',
        'total_amount',
        'payment_method',
        'is_paid',
        'order_status',
        'created_at',
    )
    list_filter = ('order_status', 'is_paid', 'payment_method')
    search_fields = ('id', 'billing_address__first_name', 'billing_address__email')

