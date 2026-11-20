from django.urls import path
from myapp import views # type: ignore
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('password-reset/', views.password_reset_request, name='password_reset'),
    path('password-reset/verify/', views.verify_password_reset_otp, name='verify_password_reset_otp'),
    path('password-reset/new-password/', views.reset_password, name='reset_password'),
    path('password-reset/success/', views.password_reset_success, name='password_reset_success'),
    path('index/', views.index, name='index'),
    path('contact/', views.contact, name='contact'),
    path('contact/contact.php', views.contact, name='contact_php_nested'),
    path('contact.php', views.contact, name='contact_php'),
    path('cart/', views.cart, name='cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('razorpay-verify/', views.razorpay_verify, name='razorpay_verify'),
    path('upi-verify/', views.upi_verify, name='upi_verify'),
    path('order-receipt/<int:order_id>/', views.order_receipt, name='order_receipt'),
    path('detail/<int:id>/', views.detail, name='detail'),
    path('shop/', views.shop, name='shop'),
    path('add-to-cart/<int:id>/', views.add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<int:id>/', views.remove_from_cart, name='remove_from_cart'),
    path('update-cart/<int:id>/', views.update_cart, name='update_cart'),
    path('apply-coupon/', views.apply_coupon, name='apply_coupon'),
    path('remove-coupon/', views.remove_coupon, name='remove_coupon'),
    path('manage-account/', views.manage_account, name='manage_account'),
    path('logout/', views.user_logout, name='logout'),

    # Custom Frontend Admin Dashboard & Inventory Panel
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/login/', views.admin_login, name='admin_panel_login'),
    path('admin-dashboard/product/add/', views.admin_product_add, name='admin_product_add'),
    path('admin-dashboard/product/edit/<int:id>/', views.admin_product_edit, name='admin_product_edit'),
    path('admin-dashboard/product/delete/<int:id>/', views.admin_product_delete, name='admin_product_delete'),
    path('admin-dashboard/product/update-stock/<int:id>/', views.admin_product_update_stock, name='admin_product_update_stock'),
    path('admin-dashboard/order/<int:id>/status/', views.admin_order_status_update, name='admin_order_status_update'),
    path('admin-dashboard/coupon/add/', views.admin_coupon_add, name='admin_coupon_add'),
    path('admin-dashboard/coupon/toggle/<int:id>/', views.admin_coupon_toggle, name='admin_coupon_toggle'),
    path('admin-dashboard/coupon/delete/<int:id>/', views.admin_coupon_delete, name='admin_coupon_delete'),
    path('admin-dashboard/message/toggle/<int:id>/', views.admin_message_toggle_read, name='admin_message_toggle_read'),
    
    # Real-time stock API
    path('api/products/live-stock/', views.api_live_stock, name='api_live_stock'),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)