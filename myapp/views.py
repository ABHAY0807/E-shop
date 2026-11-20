import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
import razorpay
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
from django.shortcuts import render, redirect, get_object_or_404
import razorpay
from .models import *
from django.core.paginator import Paginator
import json

# Create your views here.

def login(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser or request.user.username == 'admin':
            return redirect('/admin-dashboard/?tab=products')
        return redirect('index')

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

                # When logging in with admin credentials, directly open the Admin Panel for managing products
                if authenticated_user.is_staff or authenticated_user.is_superuser or authenticated_user.username == 'admin':
                    return redirect('/admin-dashboard/?tab=products')

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

@csrf_exempt
def contact(request):
    categories = Categories.objects.all()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        is_ajax = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest' or
            request.POST.get('is_ajax') == 'true'
        )

        if not name or not email or not subject or not message:
            error_msg = 'Please fill in all required fields (Name, Email, Subject, and Message).'
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
            messages.error(request, error_msg)
            return render(request, 'contact.html', {'categories': categories})

        # Save to database so message is permanently stored
        contact_record = ContactMessage.objects.create(
            name=name,
            email=email,
            subject=subject,
            message=message
        )

        # Prepare and send email to admin (abhaysolanki5902@gmail.com)
        admin_recipient = getattr(settings, 'CONTACT_EMAIL_RECIPIENT', 'abhaysolanki5902@gmail.com')
        email_subject = f"[EShopper Contact] {subject} - From {name}"
        email_body = (
            f"Hello Abhay,\n\n"
            f"You received a new inquiry from the Contact Us form on EShopper:\n\n"
            f"--------------------------------------------------\n"
            f"Sender Name   : {name}\n"
            f"Sender Email  : {email}\n"
            f"Subject       : {subject}\n"
            f"Date & Time   : {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"--------------------------------------------------\n\n"
            f"Message:\n"
            f"{message}\n\n"
            f"--------------------------------------------------\n"
            f"Note: To reply directly to {name}, simply reply to this email."
        )

        try:
            email_msg = EmailMessage(
                subject=email_subject,
                body=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL or 'abhaysolanki5902@gmail.com',
                to=[admin_recipient],
                reply_to=[email],
            )
            email_msg.send(fail_silently=False)
        except Exception as e:
            # Contact message is safely preserved in database, log warning
            print(f"[Warning] Email sending failed: {e}")

        success_msg = f'Thank you, {name}! Your message has been sent successfully.'
        if is_ajax:
            return JsonResponse({'status': 'success', 'message': success_msg})

        messages.success(request, success_msg)
        return redirect('contact')

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

    # Read applied coupon from session, but strictly validate that it is not expired
    coupon_id = request.session.get('coupon_id')
    coupon = None
    discount = Decimal('0.00')

    if coupon_id and cart_items.exists():
        coupon = Coupons.objects.filter(id=coupon_id).first()
        if coupon and coupon.is_valid():
            discount = (subtotal * coupon.discount / Decimal('100')).quantize(
                Decimal('0.01')
            )
        else:
            # Auto-remove expired or invalid old coupons from session
            request.session.pop('coupon_id', None)
            coupon = None
            discount = Decimal('0.00')
    elif coupon_id and not cart_items.exists():
        # Cart is empty, clean coupon
        request.session.pop('coupon_id', None)
        coupon = None
        discount = Decimal('0.00')

    # Never allow discount to exceed subtotal
    discount = min(discount, subtotal)
    grand_total = subtotal + shipping - discount

    # Retrieve all coupons and evaluate validity
    all_coupons = Coupons.objects.all().order_by('-id')
    active_coupons = [c for c in all_coupons if c.is_valid()]
    expired_coupons = [c for c in all_coupons if not c.is_valid()]

    context = {
        'categories': categories,
        'cart_items': cart_items,
        'total': subtotal,
        'shipping': shipping,
        'coupon': coupon,
        'discount': discount,
        'grand_total': grand_total,
        'active_coupons': active_coupons,
        'expired_coupons': expired_coupons,
    }

    return render(request, 'cart.html', context)

def apply_coupon(request):
    if request.method != 'POST':
        return redirect('cart')

    coupon_code = request.POST.get('coupon_code', '').strip()

    if not coupon_code:
        messages.error(request, "Please enter a coupon code.")
        return redirect('cart')

    # Check whether the cart contains items
    if not CartItem.objects.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('cart')

    # Find the coupon (case-insensitive)
    coupon = Coupons.objects.filter(
        code__iexact=coupon_code
    ).first()

    # Check whether the coupon exists
    if not coupon:
        messages.error(request, "Invalid coupon code.")
        return redirect('cart')

    # Check whether coupon is valid and active
    if not coupon.is_valid():
        if coupon.is_expired():
            messages.error(request, "This coupon has expired.")
        elif not coupon.active:
            messages.error(request, "This coupon is inactive.")
        elif coupon.start_date > timezone.now():
            messages.error(request, "This coupon is not available yet.")
        else:
            messages.error(request, "This coupon has an invalid discount or configuration.")
        return redirect('cart')

    # Apply the valid coupon
    request.session['coupon_id'] = coupon.id

    messages.success(
        request,
        f"Coupon {coupon.code} applied successfully! "
        f"You received {coupon.discount}% discount."
    )

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
    cart_item = get_object_or_404(CartItem, id=id)

    if request.method == "POST":
        action = request.POST.get('action')
        try:
            quantity = int(request.POST.get('quantity', cart_item.quantity))
        except (ValueError, TypeError):
            quantity = cart_item.quantity

        if action == 'plus':
            quantity = cart_item.quantity + 1
        elif action == 'minus':
            quantity = cart_item.quantity - 1

        if quantity <= 0:
            cart_item.delete()
            messages.info(request, f"Removed '{cart_item.product.name}' from your cart.")
            return redirect('cart')

        if cart_item.product and quantity > cart_item.product.stock:
            messages.error(request, f"Cannot update quantity. Only {cart_item.product.stock} unit(s) available for '{cart_item.product.name}'.")
            return redirect('cart')

        cart_item.quantity = quantity
        cart_item.save()

    return redirect('cart')

def remove_from_cart(request, id):
    cart_item = CartItem.objects.get(id=id)
    cart_item.delete()
    return redirect('cart')


def deduct_order_stock(order):
    """
    Atomically decreases product stock when an order is placed/confirmed.
    Guarded by order.stock_deducted flag to avoid double deduction.
    """
    if getattr(order, 'stock_deducted', False):
        return

    from django.db import transaction
    with transaction.atomic():
        for item in order.items.select_related('product').all():
            if item.product:
                prod = Product.objects.select_for_update().get(id=item.product.id)
                prod.stock = max(0, prod.stock - item.quantity)
                prod.save(update_fields=['stock'])

        order.stock_deducted = True
        order.save(update_fields=['stock_deducted'])


def restore_order_stock(order):
    """
    Atomically restores product stock if an order is cancelled.
    """
    if not getattr(order, 'stock_deducted', False):
        return

    from django.db import transaction
    with transaction.atomic():
        for item in order.items.select_related('product').all():
            if item.product:
                prod = Product.objects.select_for_update().get(id=item.product.id)
                prod.stock += item.quantity
                prod.save(update_fields=['stock'])

        order.stock_deducted = False
        order.save(update_fields=['stock_deducted'])


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

    saved_billing = None
    if request.user.is_authenticated:
        saved_billing = BillingAddress.objects.filter(user=request.user).order_by('-created_at').first()

    if request.method == 'POST':
        if not cart_items.exists():
            messages.error(request, "Your cart is empty. Please add items before checking out.")
            return redirect('cart')

        is_ajax = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest' or
            request.POST.get('is_ajax') == 'true'
        )

        # Real-time stock validation: check if available stock is sufficient for all cart items
        for item in cart_items:
            if item.product and item.product.stock < item.quantity:
                stock_err = f"Sorry, '{item.product.name}' only has {item.product.stock} unit(s) available in stock. Please adjust your cart quantity."
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': stock_err}, status=400)
                messages.error(request, stock_err)
                return redirect('cart')

        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        mobile_no = request.POST.get('mobile_no', '').strip()
        address_line1 = request.POST.get('address_line1', '').strip()
        address_line2 = request.POST.get('address_line2', '').strip()
        country = request.POST.get('country', 'India').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        zip_code = request.POST.get('zip_code', '').strip()
        payment_method = request.POST.get('payment', 'Razorpay').strip()

        if not first_name or not last_name or not email or not mobile_no or not address_line1 or not city or not state or not zip_code:
            error_msg = "Please fill in all required billing address fields."
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('checkout')

        # Save billing address
        billing_address = BillingAddress.objects.create(
            user=request.user if request.user.is_authenticated else None,
            first_name=first_name,
            last_name=last_name,
            email=email,
            mobile_no=mobile_no,
            address_line1=address_line1,
            address_line2=address_line2,
            country=country,
            city=city,
            state=state,
            zip_code=zip_code,
        )

        # Create Order
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            billing_address=billing_address,
            subtotal=subtotal,
            shipping=shipping,
            discount=discount,
            total_amount=total,
            payment_method=payment_method,
            is_paid=False,
            order_status='Pending'
        )

        # Snapshot cart items into OrderItem
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                product_name=item.product.name,
                price=item.product.price,
                quantity=item.quantity,
                total_price=item.total_price()
            )

        amount_in_paise = int(total * 100)

        if payment_method == 'Razorpay':
            rzp_order_id = None
            is_real_razorpay = False
            try:
                client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                rzp_order = client.order.create({
                    'amount': amount_in_paise,
                    'currency': 'INR',
                    'receipt': order.receipt_number,
                    'payment_capture': 1
                })
                rzp_order_id = rzp_order.get('id')
                order.razorpay_order_id = rzp_order_id
                order.save(update_fields=['razorpay_order_id'])
                is_real_razorpay = True
            except Exception as e:
                print(f"[Razorpay Server Order Note]: {e}")

            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'payment_method': 'Razorpay',
                    'order_id': order.id,
                    'razorpay_order_id': rzp_order_id,
                    'amount': amount_in_paise,
                    'currency': 'INR',
                    'key_id': settings.RAZORPAY_KEY_ID,
                    'receipt_number': order.receipt_number,
                    'customer_name': f"{first_name} {last_name}",
                    'customer_email': email,
                    'customer_phone': mobile_no,
                    'use_simulator': not is_real_razorpay,
                })

            return render(request, 'razorpay_payment.html', {
                'order': order,
                'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                'amount_in_paise': amount_in_paise,
                'razorpay_order_id': rzp_order_id,
                'categories': categories,
            })

        elif payment_method == 'BHIM UPI':
            from urllib.parse import quote_plus
            upi_id = getattr(settings, 'MERCHANT_UPI_ID', 'abhaysolanki5902@okhdfcbank')
            upi_name = getattr(settings, 'MERCHANT_UPI_NAME', 'EShopper Store')
            encoded_name = quote_plus(upi_name)
            encoded_note = quote_plus(f"Order #{order.id} {order.receipt_number}")
            upi_deep_link = f"upi://pay?pa={upi_id}&pn={encoded_name}&am={total}&cu=INR&tn={encoded_note}"
            qr_api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=260x260&data={quote_plus(upi_deep_link)}"

            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'payment_method': 'BHIM UPI',
                    'order_id': order.id,
                    'receipt_number': order.receipt_number,
                    'amount': float(total),
                    'upi_id': upi_id,
                    'upi_name': upi_name,
                    'upi_deep_link': upi_deep_link,
                    'qr_api_url': qr_api_url,
                    'customer_name': f"{first_name} {last_name}",
                })

            return render(request, 'upi_payment.html', {
                'order': order,
                'upi_id': upi_id,
                'upi_name': upi_name,
                'upi_deep_link': upi_deep_link,
                'qr_api_url': qr_api_url,
                'categories': categories,
            })

        else:
            # Cash on delivery / Direct check
            deduct_order_stock(order)
            CartItem.objects.all().delete()
            request.session.pop('coupon_id', None)

            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'payment_method': payment_method,
                    'redirect_url': f'/order-receipt/{order.id}/'
                })

            messages.success(request, f"Order placed successfully! Receipt #{order.receipt_number}")
            return redirect('order_receipt', order_id=order.id)

    context = {
        'categories': categories,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping': shipping,
        'coupon': coupon,
        'discount': discount,
        'total': total,
        'saved_billing': saved_billing,
        'razorpay_key_id': getattr(settings, 'RAZORPAY_KEY_ID', 'rzp_test_U1zVcgfC6rteVZ'),
        'amount_in_paise': int(total * 100),
        'merchant_upi_id': getattr(settings, 'MERCHANT_UPI_ID', 'abhaysolanki5902@okhdfcbank'),
        'merchant_upi_name': getattr(settings, 'MERCHANT_UPI_NAME', 'EShopper Store'),
    }

    return render(request, 'checkout.html', context)


@csrf_exempt
def razorpay_verify(request):
    if request.method != 'POST':
        return redirect('cart')

    is_ajax = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
        request.POST.get('is_ajax') == 'true'
    )

    order_id = request.POST.get('order_id')
    razorpay_payment_id = request.POST.get('razorpay_payment_id', '').strip()
    razorpay_order_id = request.POST.get('razorpay_order_id', '').strip()
    razorpay_signature = request.POST.get('razorpay_signature', '').strip()

    if not order_id or not razorpay_payment_id:
        error_msg = "Invalid payment data received."
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect('checkout')

    order = get_object_or_404(Order, id=order_id)

    # Verify signature if signature & secret are available
    if razorpay_signature and razorpay_order_id:
        try:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })
        except Exception as e:
            print(f"[Razorpay Signature Notice]: {e}")

    # Mark order as paid
    order.is_paid = True
    order.order_status = 'Processing'
    order.razorpay_payment_id = razorpay_payment_id
    if razorpay_order_id:
        order.razorpay_order_id = razorpay_order_id
    if razorpay_signature:
        order.razorpay_signature = razorpay_signature
    order.save()

    # Deduct product stock in real time
    deduct_order_stock(order)

    # Clear Cart & Coupon
    CartItem.objects.all().delete()
    request.session.pop('coupon_id', None)

    messages.success(request, f"Payment successful! Order #{order.id} confirmed.")

    redirect_url = f"/order-receipt/{order.id}/"
    if is_ajax:
        return JsonResponse({'status': 'success', 'redirect_url': redirect_url})

    return redirect('order_receipt', order_id=order.id)


@csrf_exempt
def upi_verify(request):
    if request.method != 'POST':
        return redirect('cart')

    is_ajax = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
        request.POST.get('is_ajax') == 'true'
    )

    order_id = request.POST.get('order_id')
    upi_transaction_id = request.POST.get('upi_transaction_id', '').strip()

    if not order_id:
        error_msg = "Invalid order data received."
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect('checkout')

    order = get_object_or_404(Order, id=order_id)

    if not upi_transaction_id:
        date_str = timezone.now().strftime('%Y%m%d%H%M')
        upi_transaction_id = f"UPI{date_str}{secrets.token_hex(2).upper()}"

    order.is_paid = True
    order.order_status = 'Processing'
    order.payment_method = 'BHIM UPI'
    order.upi_transaction_id = upi_transaction_id
    order.save()

    # Deduct product stock in real time
    deduct_order_stock(order)

    # Clear Cart & Coupon
    CartItem.objects.all().delete()
    request.session.pop('coupon_id', None)

    messages.success(request, f"UPI payment confirmed! Order #{order.id} is now processing.")

    redirect_url = f"/order-receipt/{order.id}/"
    if is_ajax:
        return JsonResponse({'status': 'success', 'redirect_url': redirect_url})

    return redirect('order_receipt', order_id=order.id)


def order_receipt(request, order_id):
    categories = Categories.objects.all()
    order = get_object_or_404(Order, id=order_id)
    items = order.items.all()

    context = {
        'categories': categories,
        'order': order,
        'items': items,
        'billing': order.billing_address,
    }
    return render(request, 'order_receipt.html', context)


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
        from django.db.models import Q
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(subcategory__name__icontains=search_query) |
            Q(subcategory__category__name__icontains=search_query)
        ).distinct()

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

    shop_carousel_items = ShopCarousel.objects.filter(is_active=True)

    context = {
        'categories': categories,
        'colors': colors,
        'sizes': sizes,
        'products': products,
        'selected_category': category_id,
        'selected_subcategory': subcategory_id,
        'search_query': search_query or '',
        'shop_carousel_items': shop_carousel_items,
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


@login_required(login_url='login')
def manage_account(request):
    categories = Categories.objects.all()
    user = request.user

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()

            if not email:
                messages.error(request, 'Email address cannot be empty.')
            else:
                existing = User.objects.filter(email__iexact=email).exclude(id=user.id).first()
                if existing:
                    messages.error(request, 'This email address is already used by another account.')
                else:
                    user.first_name = first_name
                    user.last_name = last_name
                    user.email = email
                    user.save()
                    messages.success(request, 'Your profile details have been updated successfully!')
            return redirect('manage_account')

        elif action == 'change_password':
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not user.check_password(current_password):
                messages.error(request, 'The current password you entered is incorrect.')
            elif len(new_password) < 6:
                messages.error(request, 'New password must be at least 6 characters long.')
            elif new_password != confirm_password:
                messages.error(request, 'The new password and confirm password do not match.')
            else:
                user.set_password(new_password)
                user.save()
                auth_login(request, user)
                messages.success(request, 'Password changed successfully!')
            return redirect('manage_account')

    user_orders = Order.objects.filter(user=user).order_by('-created_at')

    context = {
        'categories': categories,
        'user': user,
        'user_orders': user_orders,
    }
    return render(request, 'manage_account.html', context)


def user_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


# ==========================================
# CUSTOM FRONTEND ADMIN DASHBOARD & PANEL
# ==========================================

def is_admin_or_staff(user):
    return user.is_authenticated and (
        user.is_staff or user.is_superuser or user.username == 'admin'
    )


def admin_login(request):
    """Dedicated login view for the Custom Admin Dashboard."""
    if is_admin_or_staff(request.user):
        return redirect('admin_dashboard')

    if request.method == 'POST':
        username_or_email = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = User.objects.filter(email__iexact=username_or_email).first()
        if not user:
            user = User.objects.filter(username__iexact=username_or_email).first()

        if user:
            authenticated_user = authenticate(request, username=user.username, password=password)
            if authenticated_user:
                if is_admin_or_staff(authenticated_user):
                    auth_login(request, authenticated_user)
                    messages.success(request, f"Welcome back to Admin Dashboard, {authenticated_user.username}!")
                    return redirect('admin_dashboard')
                else:
                    messages.error(request, "Access Denied: This account does not have administrator / staff privileges.")
                    return render(request, 'admin_login.html')

        messages.error(request, "Invalid administrator credentials.")

    return render(request, 'admin_login.html')


def admin_dashboard(request):
    """Main Custom Frontend Admin Dashboard."""
    if not is_admin_or_staff(request.user):
        messages.warning(request, "Please log in with an administrator or staff account to access the Admin Panel.")
        return redirect('admin_panel_login')

    from django.db.models import Sum

    # Inventory & Product Metrics
    total_products = Product.objects.count()
    total_stock = Product.objects.aggregate(total=Sum('stock'))['total'] or 0
    low_stock_products = Product.objects.filter(stock__lte=5).select_related('subcategory', 'color', 'size').order_by('stock')
    out_of_stock_count = Product.objects.filter(stock=0).count()

    # Order & Revenue Metrics
    total_orders = Order.objects.count()
    total_revenue = Order.objects.filter(is_paid=True).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    orders_pending = Order.objects.filter(order_status='Pending').count()
    orders_processing = Order.objects.filter(order_status='Processing').count()
    orders_shipped = Order.objects.filter(order_status='Shipped').count()
    orders_delivered = Order.objects.filter(order_status='Delivered').count()
    orders_cancelled = Order.objects.filter(order_status='Cancelled').count()

    # Data collections
    products = Product.objects.select_related('subcategory', 'subcategory__category', 'color', 'size').order_by('-id')
    orders = Order.objects.select_related('billing_address').prefetch_related('items').order_by('-created_at')
    coupons = Coupons.objects.order_by('-id')
    messages_list = ContactMessage.objects.order_by('-created_at')

    # Dropdown references for modals
    categories = Categories.objects.all()
    subcategories = Subcategories.objects.select_related('category').all()
    colors = Colors.objects.all()
    sizes = Sizes.objects.all()

    active_tab = request.GET.get('tab', 'overview')

    context = {
        'total_products': total_products,
        'total_stock': total_stock,
        'low_stock_products': low_stock_products,
        'out_of_stock_count': out_of_stock_count,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'orders_pending': orders_pending,
        'orders_processing': orders_processing,
        'orders_shipped': orders_shipped,
        'orders_delivered': orders_delivered,
        'orders_cancelled': orders_cancelled,
        'products': products,
        'orders': orders,
        'coupons': coupons,
        'messages_list': messages_list,
        'categories': categories,
        'subcategories': subcategories,
        'colors': colors,
        'sizes': sizes,
        'active_tab': active_tab,
    }
    return render(request, 'admin_dashboard.html', context)


def admin_product_add(request):
    """Add a new product with variant and initial stock."""
    if not is_admin_or_staff(request.user):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        subcategory_id = request.POST.get('subcategory')
        color_id = request.POST.get('color') or None
        size_id = request.POST.get('size') or None
        price = request.POST.get('price', '0').strip()
        stock = request.POST.get('stock', '0').strip()
        image = request.FILES.get('image')

        if not name or not subcategory_id or not price:
            messages.error(request, "Product name, subcategory, and price are required.")
            return redirect('/admin-dashboard/?tab=products')

        try:
            subcategory = Subcategories.objects.get(id=subcategory_id)
            color = Colors.objects.get(id=color_id) if color_id else None
            size = Sizes.objects.get(id=size_id) if size_id else None
            price_dec = Decimal(price)
            stock_int = max(0, int(stock))

            product = Product.objects.create(
                name=name,
                subcategory=subcategory,
                color=color,
                size=size,
                price=price_dec,
                stock=stock_int,
                image=image
            )
            messages.success(request, f"Product '{product.name}' created successfully with {stock_int} in stock!")
        except Exception as e:
            messages.error(request, f"Error creating product: {e}")

    return redirect('/admin-dashboard/?tab=products')


def admin_product_edit(request, id):
    """Update an existing product's details, pricing, and stock."""
    if not is_admin_or_staff(request.user):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    product = get_object_or_404(Product, id=id)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        subcategory_id = request.POST.get('subcategory')
        color_id = request.POST.get('color') or None
        size_id = request.POST.get('size') or None
        price = request.POST.get('price', '').strip()
        stock = request.POST.get('stock', '').strip()
        image = request.FILES.get('image')

        if name:
            product.name = name
        if subcategory_id:
            product.subcategory_id = subcategory_id
        product.color_id = color_id if color_id else None
        product.size_id = size_id if size_id else None
        if price:
            product.price = Decimal(price)
        if stock:
            product.stock = max(0, int(stock))
        if image:
            product.image = image

        product.save()
        messages.success(request, f"Product #{product.id} ('{product.name}') updated successfully!")

    return redirect('/admin-dashboard/?tab=products')


def admin_product_delete(request, id):
    """Delete a product."""
    if not is_admin_or_staff(request.user):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    product = get_object_or_404(Product, id=id)
    prod_name = product.name
    product.delete()
    messages.success(request, f"Product '{prod_name}' (ID #{id}) has been deleted.")
    return redirect('/admin-dashboard/?tab=products')


def admin_product_update_stock(request, id):
    """Quick in-line quantity updater for instant inventory management without page reload."""
    if not is_admin_or_staff(request.user):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    product = get_object_or_404(Product, id=id)

    if request.method == 'POST':
        action = request.POST.get('action')  # 'increment', 'decrement', 'set'
        amount = int(request.POST.get('amount', 1))

        if action == 'increment':
            product.stock += amount
        elif action == 'decrement':
            product.stock = max(0, product.stock - amount)
        elif action == 'set':
            product.stock = max(0, amount)

        product.save(update_fields=['stock'])

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == 'true':
            return JsonResponse({
                'status': 'success',
                'id': product.id,
                'stock': product.stock,
                'is_in_stock': product.stock > 0,
                'message': f"Stock for '{product.name}' updated to {product.stock} units."
            })

        messages.success(request, f"Stock for '{product.name}' updated to {product.stock} units.")

    return redirect('/admin-dashboard/?tab=products')


def admin_order_status_update(request, id):
    """Update order fulfillment status and payment state."""
    if not is_admin_or_staff(request.user):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    order = get_object_or_404(Order, id=id)

    if request.method == 'POST':
        new_status = request.POST.get('order_status')
        new_paid = request.POST.get('is_paid')

        if new_status in ['Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled']:
            prev_status = order.order_status
            order.order_status = new_status
            if new_status == 'Cancelled' and prev_status != 'Cancelled':
                restore_order_stock(order)
            elif prev_status == 'Cancelled' and new_status != 'Cancelled':
                deduct_order_stock(order)
            elif new_status in ['Processing', 'Shipped', 'Delivered'] and not getattr(order, 'stock_deducted', False):
                deduct_order_stock(order)

        if new_paid is not None:
            order.is_paid = (new_paid.lower() in ['true', '1', 'paid', 'yes'])

        order.save()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == 'true':
            return JsonResponse({
                'status': 'success',
                'order_id': order.id,
                'order_status': order.order_status,
                'is_paid': order.is_paid,
                'message': f"Order #{order.id} status updated to {order.order_status}."
            })

        messages.success(request, f"Order #{order.id} updated successfully.")

    return redirect('/admin-dashboard/?tab=orders')


def admin_coupon_add(request):
    """Create a new promotional coupon directly from the Admin Panel."""
    if not is_admin_or_staff(request.user):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    if request.method == 'POST':
        code = request.POST.get('code', '').strip().upper()
        discount = request.POST.get('discount', '10').strip()
        duration = request.POST.get('duration', 'custom')

        if not code or not discount:
            messages.error(request, "Coupon code and discount percentage are required.")
            return redirect('/admin-dashboard/?tab=coupons')

        if Coupons.objects.filter(code__iexact=code).exists():
            messages.error(request, f"Coupon code '{code}' already exists.")
            return redirect('/admin-dashboard/?tab=coupons')

        try:
            coupon = Coupons.objects.create(
                code=code,
                discount=Decimal(discount),
                duration=duration,
                active=True,
                start_date=timezone.now()
            )
            messages.success(request, f"Coupon '{coupon.code}' with {coupon.discount}% discount created successfully!")
        except Exception as e:
            messages.error(request, f"Error creating coupon: {e}")

    return redirect('/admin-dashboard/?tab=coupons')


def admin_coupon_toggle(request, id):
    """Toggle coupon active/inactive status."""
    if not is_admin_or_staff(request.user):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    coupon = get_object_or_404(Coupons, id=id)
    coupon.active = not coupon.active
    coupon.save(update_fields=['active'])
    status_str = "activated" if coupon.active else "deactivated"
    messages.success(request, f"Coupon '{coupon.code}' has been {status_str}.")
    return redirect('/admin-dashboard/?tab=coupons')


def admin_coupon_delete(request, id):
    """Delete a coupon."""
    if not is_admin_or_staff(request.user):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    coupon = get_object_or_404(Coupons, id=id)
    code = coupon.code
    coupon.delete()
    messages.success(request, f"Coupon '{code}' has been deleted.")
    return redirect('/admin-dashboard/?tab=coupons')


def admin_message_toggle_read(request, id):
    """Toggle contact message read/unread status."""
    if not is_admin_or_staff(request.user):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    msg = get_object_or_404(ContactMessage, id=id)
    msg.is_read = not msg.is_read
    msg.save(update_fields=['is_read'])
    state = "marked as read" if msg.is_read else "marked as unread"
    messages.success(request, f"Inquiry from {msg.name} {state}.")
    return redirect('/admin-dashboard/?tab=messages')


@csrf_exempt
def api_live_stock(request):
    """
    Real-time stock endpoint for live updates.
    Returns product stock, price, out of stock status, and summary metrics.
    """
    product_id = request.GET.get('product_id')
    if product_id:
        prod = Product.objects.filter(id=product_id).first()
        if not prod:
            return JsonResponse({'status': 'error', 'message': 'Product not found'}, status=404)
        return JsonResponse({
            'status': 'success',
            'product': {
                'id': prod.id,
                'name': prod.name,
                'stock': prod.stock,
                'price': float(prod.price),
                'in_stock': prod.stock > 0,
            }
        })

    products = list(Product.objects.all().values('id', 'name', 'stock', 'price'))
    total_stock = sum(p['stock'] for p in products)
    low_stock_count = sum(1 for p in products if 0 < p['stock'] <= 5)
    out_of_stock_count = sum(1 for p in products if p['stock'] == 0)

    return JsonResponse({
        'status': 'success',
        'total_products': len(products),
        'total_stock': total_stock,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'products': products
    })



@csrf_exempt
def api_live_stock(request):
    """
    Real-time stock endpoint for live updates.
    Returns product stock, price, out of stock status, and summary metrics.
    """
    product_id = request.GET.get('product_id')
    if product_id:
        prod = Product.objects.filter(id=product_id).first()
        if not prod:
            return JsonResponse({'status': 'error', 'message': 'Product not found'}, status=404)
        return JsonResponse({
            'status': 'success',
            'product': {
                'id': prod.id,
                'name': prod.name,
                'stock': prod.stock,
                'price': float(prod.price),
                'in_stock': prod.stock > 0,
            }
        })

    products = list(Product.objects.all().values('id', 'name', 'stock', 'price'))
    total_stock = sum(p['stock'] for p in products)
    low_stock_count = sum(1 for p in products if 0 < p['stock'] <= 5)
    out_of_stock_count = sum(1 for p in products if p['stock'] == 0)

    return JsonResponse({
        'status': 'success',
        'total_products': len(products),
        'total_stock': total_stock,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'products': products
    })