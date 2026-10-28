import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone

from .models import PasswordResetOTP



from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.http import request
from decimal import Decimal
from django.shortcuts import render, redirect
from .models import *
from django.core.paginator import Paginator
import json

# Create your views here.

def login(request):
    if request.method == 'POST':
        username_or_email = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me')

        # Find the registered user by username or email.
        user = User.objects.filter(
            email__iexact=username_or_email
        ).first()

        if user is None:
            user = User.objects.filter(
                username__iexact=username_or_email
            ).first()

        if user:
            authenticated_user = authenticate(
                request,
                username=user.username,
                password=password
            )

            if authenticated_user is not None:
                auth_login(request, authenticated_user)

                # Keep the user logged in according to their choice.
                if remember_me:
                    request.session.set_expiry(1209600)  # 2 weeks
                else:
                    request.session.set_expiry(0)  # Until browser closes

                messages.success(request, 'Login successful!')
                return redirect('index')

        messages.error(
            request,
            'Invalid username/email or password.'
        )

    return render(request, 'login.html')


def register(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        # Check that all fields are filled.
        if not username or not email or not password1 or not password2:
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'register.html')

        # Check whether the username already exists.
        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, 'This username is already registered.')
            return render(request, 'register.html')

        # Check whether the email already exists.
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, 'This email is already registered.')
            return render(request, 'register.html')

        # Check whether the passwords match.
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'register.html')

        # Validate the password using Django's password validators.
        try:
            validate_password(password1)
        except ValidationError as error:
            for message in error.messages:
                messages.error(request, message)
            return render(request, 'register.html')

        # Save the new user securely.
        User.objects.create_user(
            username=username,
            email=email,
            password=password1
        )

        messages.success(
            request,
            'Registration successful! You can now log in.'
        )
        return redirect('login')

    return render(request, 'register.html')


def password_reset_request(request):
    """Send a six-digit OTP to the account's registered email address."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        user = User.objects.filter(email__iexact=email).first() if email else None

        # Use a generic response so the page does not reveal registered emails.
        if user:
            otp = f"{secrets.randbelow(1_000_000):06d}"
            otp_record, _ = PasswordResetOTP.objects.update_or_create(
                user=user,
                defaults={
                    'otp_hash': make_password(otp),
                    'expires_at': timezone.now() + timedelta(minutes=5),
                    'attempts': 0,
                    'verified': False,
                },
            )

            try:
                send_mail(
                    subject='Your Password Reset OTP',
                    message=(
                        f'Your password reset OTP is {otp}.\n\n'
                        'It expires in 5 minutes. Do not share it with anyone.'
                    ),
                    from_email=None,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                request.session['password_reset_email'] = user.email
                request.session.pop('password_reset_user_id', None)
            except Exception:
                otp_record.delete()
                request.session.pop('password_reset_email', None)
                request.session.pop('password_reset_user_id', None)
                messages.error(
                    request,
                    'Unable to send the OTP right now. Please check email settings and try again.',
                )
                return render(request, 'password_reset.html')

        messages.info(
            request,
            'If the email is registered, a password reset OTP has been sent.',
        )
        return redirect('verify_password_reset_otp')

    return render(request, 'password_reset.html')


def verify_password_reset_otp(request):
    """Verify the OTP, allowing no more than five attempts."""
    email = request.session.get('password_reset_email')
    if not email:
        messages.error(request, 'Please request a password reset OTP first.')
        return redirect('password_reset')

    user = User.objects.filter(email__iexact=email).first()
    if not user:
        request.session.pop('password_reset_email', None)
        return redirect('password_reset')

    otp_record = PasswordResetOTP.objects.filter(user=user).first()
    if not otp_record:
        messages.error(request, 'Please request a new OTP.')
        request.session.pop('password_reset_email', None)
        return redirect('password_reset')

    if otp_record.is_expired():
        otp_record.delete()
        request.session.pop('password_reset_email', None)
        messages.error(request, 'Your OTP has expired. Please request a new one.')
        return redirect('password_reset')

    if request.method == 'POST':
        otp = request.POST.get('otp', '').strip()

        if otp_record.attempts >= 5:
            otp_record.delete()
            request.session.pop('password_reset_email', None)
            messages.error(
                request,
                'Too many incorrect attempts. Please request a new OTP.',
            )
            return redirect('password_reset')

        otp_record.attempts += 1
        otp_record.save(update_fields=['attempts'])

        if not check_password(otp, otp_record.otp_hash):
            if otp_record.attempts >= 5:
                otp_record.delete()
                request.session.pop('password_reset_email', None)
                messages.error(
                    request,
                    'Too many incorrect attempts. Please request a new OTP.',
                )
                return redirect('password_reset')

            messages.error(request, 'Invalid OTP. Please try again.')
            return render(request, 'verify_password_reset_otp.html')

        otp_record.verified = True
        otp_record.save(update_fields=['verified'])
        request.session['password_reset_user_id'] = user.pk
        return redirect('reset_password')

    return render(request, 'verify_password_reset_otp.html')


def reset_password(request):
    """Allow a password change only after successful OTP verification."""
    user_id = request.session.get('password_reset_user_id')
    if not user_id:
        messages.error(request, 'Please verify your OTP first.')
        return redirect('password_reset')

    user = User.objects.filter(pk=user_id).first()
    if not user:
        request.session.pop('password_reset_user_id', None)
        request.session.pop('password_reset_email', None)
        return redirect('password_reset')

    otp_record = PasswordResetOTP.objects.filter(user=user).first()
    if not otp_record or not otp_record.verified or otp_record.is_expired():
        if otp_record:
            otp_record.delete()
        request.session.pop('password_reset_user_id', None)
        request.session.pop('password_reset_email', None)
        messages.error(
            request,
            'Your verification has expired. Please request a new OTP.',
        )
        return redirect('password_reset')

    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if password1 != password2:
            messages.error(request, 'The passwords do not match.')
            return render(request, 'reset_password.html')

        try:
            validate_password(password1, user=user)
        except ValidationError as error:
            for error_message in error.messages:
                messages.error(request, error_message)
            return render(request, 'reset_password.html')

        user.set_password(password1)
        user.save(update_fields=['password'])
        otp_record.delete()
        request.session.pop('password_reset_user_id', None)
        request.session.pop('password_reset_email', None)
        messages.success(request, 'Your password has been reset successfully.')
        return redirect('password_reset_success')

    return render(request, 'reset_password.html')


def password_reset_success(request):
    return render(request, 'password_reset_success.html')

def index(request):
    categories = Categories.objects.all()
    products = Product.objects.all()
    featured_products = Product.objects.order_by('-id')[:8]
    recent_products = Product.objects.order_by('id')[:8]
    context = {
        'categories': categories,
        'products': products,
        'featured_products': featured_products,
        'recent_products': recent_products,
    }
    return render(request, 'index.html', context)

def contact(request):
    categories = Categories.objects.all()
    context = {
        'categories': categories
    }
    return render(request, 'contact.html', context)

def cart(request):
    categories = Categories.objects.all()
    cart_items = CartItem.objects.all()

    subtotal = sum(
        (item.total_price() for item in cart_items),
        Decimal('0.00')
    )

    shipping = Decimal('60.00') if cart_items.exists() else Decimal('0.00')

    # Read the applied coupon from the session.
    coupon_id = request.session.get('coupon_id')
    coupon = None
    discount = Decimal('0.00')

    if coupon_id and cart_items.exists():
        coupon = Coupons.objects.filter(
            id=coupon_id,
            active=True
        ).first()

        if coupon:
            discount = (subtotal * coupon.discount / Decimal('100')).quantize(
                Decimal('0.01')
            )
        else:
            request.session.pop('coupon_id', None)

    # Never allow the discount to exceed the subtotal.
    discount = min(discount, subtotal)

    grand_total = subtotal + shipping - discount

    context = {
        'categories': categories,
        'cart_items': cart_items,
        'total': subtotal,
        'shipping': shipping,
        'coupon': coupon,
        'discount': discount,
        'grand_total': grand_total,
    }

    return render(request, 'cart.html', context)

def apply_coupon(request):
    if request.method != 'POST':
        return redirect('cart')

    code = request.POST.get('coupon_code', '').strip().upper()

    if not code:
        messages.error(request, 'Please enter a coupon code.')
        return redirect('cart')

    # Don't apply coupons to an empty cart.
    if not CartItem.objects.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('cart')

    coupon = Coupons.objects.filter(
        code__iexact=code,
        active=True
    ).first()

    if not coupon:
        messages.error(request, 'Invalid or inactive coupon code.')
        return redirect('cart')

    # A percentage discount must be greater than 0 and no more than 100.
    if coupon.discount <= 0 or coupon.discount > 100:
        messages.error(request, 'This coupon has an invalid discount.')
        return redirect('cart')

    request.session['coupon_id'] = coupon.id

    messages.success(request,f'Coupon {coupon.code} applied successfully! 'f'You received a {coupon.discount}% discount.')
    return redirect('cart')

def remove_coupon(request):
    if request.method == 'POST':
        request.session.pop('coupon_id', None)
        messages.success(request, 'Coupon removed successfully.')

    return redirect('cart')

def add_to_cart(request, id):
    if request.method != 'POST':
        return redirect('detail', id=id)

    product = Product.objects.filter(id=id).first()
    if not product:
        messages.error(request, 'Product not found.')
        return redirect('shop')

    try:
        quantity = int(request.POST.get('quantity', 1))
        color_id = int(request.POST.get('color', 0))
        size_id = int(request.POST.get('size', 0))
    except (ValueError, TypeError):
        messages.error(request, 'Please select a valid colour and size.')
        return redirect('detail', id=id)

    if quantity < 1:
        messages.error(request, 'Quantity must be at least 1.')
        return redirect('detail', id=id)

    selected_product = Product.objects.filter(
        name=product.name,
        subcategory=product.subcategory,
        color_id=color_id,
        size_id=size_id
    ).first()

    if not selected_product:
        messages.error(request, 'This colour and size combination is unavailable.')
        return redirect('detail', id=id)

    if selected_product.stock < quantity:
        messages.error(request, 'This variant is out of stock or has insufficient stock.')
        return redirect('detail', id=id)

    cart_item = CartItem.objects.filter(product=selected_product).first()
    existing_quantity = cart_item.quantity if cart_item else 0

    if existing_quantity + quantity > selected_product.stock:
        messages.error(request, f'Only {selected_product.stock} item(s) are available in total.')
        return redirect('detail', id=id)

    if cart_item:
        cart_item.quantity += quantity
        cart_item.save()
    else:
        CartItem.objects.create(product=selected_product, quantity=quantity)

    messages.success(request, 'Product added to cart successfully!')
    return redirect('cart')

def update_cart(request, id):
    cart_item = CartItem.objects.get(id=id)

    if request.method == "POST":
        quantity = int(request.POST.get('quantity'))
        cart_item.quantity = quantity
        cart_item.save()

    return redirect('cart')

def remove_from_cart(request, id):
    cart_item = CartItem.objects.get(id=id)
    cart_item.delete()
    return redirect('cart')

def checkout(request):
    categories = Categories.objects.all()
    cart_items = CartItem.objects.all()

    # Calculate subtotal.
    subtotal = sum(
        (item.total_price() for item in cart_items),
        Decimal('0.00')
    )

    # Calculate shipping.
    shipping = Decimal('60.00') if cart_items.exists() else Decimal('0.00')

    # Get the applied coupon from the session.
    coupon_id = request.session.get('coupon_id')
    coupon = None
    discount = Decimal('0.00')

    if coupon_id and cart_items.exists():
        coupon = Coupons.objects.filter(
            id=coupon_id,
            active=True
        ).first()

        if coupon and Decimal('0') < coupon.discount <= Decimal('100'):
            discount = (
                subtotal * coupon.discount / Decimal('100')
            ).quantize(Decimal('0.01'))
        else:
            request.session.pop('coupon_id', None)
            coupon = None

    # Prevent the discount from exceeding the subtotal.
    discount = min(discount, subtotal)

    # Calculate the final amount.
    total = subtotal + shipping - discount

    context = {
        'categories': categories,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping': shipping,
        'coupon': coupon,
        'discount': discount,
        'total': total,
    }

    return render(request, 'checkout.html', context)

def detail(request, id):
    categories = Categories.objects.all()
    product = Product.objects.get(id=id)
    variants = Product.objects.filter(
        name=product.name,
        subcategory=product.subcategory
    ).select_related('color', 'size')
    colors = Colors.objects.all()
    sizes = Sizes.objects.all()
    variant_data = [
        {
            'id': variant.id,
            'color_id': variant.color_id,
            'size_id': variant.size_id,
            'stock': variant.stock,
        }
        for variant in variants
    ]
    context = {
        'categories': categories,
        'product': product,
        'colors': colors,
        'sizes': sizes,
        'variants': variants,
        'variant_data_json': json.dumps(variant_data),
    }
    return render(request, 'detail.html', context)

def shop(request):
    categories = Categories.objects.all()
    products = Product.objects.order_by('-id')
    colors = Colors.objects.all()
    sizes = Sizes.objects.all()

    category_id = request.GET.get('category')
    subcategory_id = request.GET.get('subcategory')
    search_query = request.GET.get('q')

    if category_id:
        products = products.filter(subcategory__category_id=category_id)
    if subcategory_id:
        products = products.filter(subcategory_id=subcategory_id)
    if search_query:
        name_products = products.filter(name__icontains=search_query)
        subcategory_products = products.filter(
            subcategory__name__icontains=search_query
        )
        category_products = products.filter(
            subcategory__category__name__icontains=search_query
        )

        products = name_products.union(
            subcategory_products,
            category_products
        ).order_by('-id')

    prices = request.GET.getlist('price')
    selected_colors = request.GET.getlist('color')
    selected_sizes = request.GET.getlist('size')

    if prices and 'all' not in prices:
        filtered_products = Product.objects.none()

        for price in prices:
            if '-' in price:
                min_price, max_price = price.split('-')
                filtered_products |= products.filter(
                    price__gte=min_price,
                    price__lte=max_price
                )
            elif price.isdigit():
                filtered_products |= products.filter(price__gte=price)

        products = filtered_products

    if selected_colors and 'all' not in selected_colors:
        products = products.filter(color_id__in=selected_colors)

    if selected_sizes and 'all' not in selected_sizes:
        products = products.filter(size_id__in=selected_sizes)

    paginator = Paginator(products, 6)
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number)

    context = {
        'categories': categories,
        'colors': colors,
        'sizes': sizes,
        'products': products,
        'selected_category': category_id,
        'selected_subcategory': subcategory_id,
        'search_query': search_query or '',
    }

    return render(request, 'shop.html', context)

def filter(products, color=None, size=None, min_price=None, max_price=None):
    if color:
        products=products.filter(color_id=color)
    if size:
        products=products.filter(size_id=size)
    if min_price:
        products=products.filter(price__gte=min_price)
    if max_price:
        products=products.filter(price__lte=max_price)
    return products