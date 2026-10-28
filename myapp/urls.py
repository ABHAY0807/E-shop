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
    path('cart/', views.cart, name='cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('detail/<int:id>/', views.detail, name='detail'),
    path('shop/', views.shop, name='shop'),
    path('add-to-cart/<int:id>/', views.add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<int:id>/', views.remove_from_cart, name='remove_from_cart'),
    path('update-cart/<int:id>/', views.update_cart, name='update_cart'),
    path('apply-coupon/', views.apply_coupon, name='apply_coupon'),
    path('remove-coupon/', views.remove_coupon, name='remove_coupon'),
    
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)