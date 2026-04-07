from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Sum, Avg, Count, Q
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.http import HttpResponseRedirect
from .models import Product, Category, User, Order, Cart, CartItem, OrderItem
from .forms import UserRegistrationForm, UserLoginForm, ProductForm, ReviewForm

def product_list(request, category_slug=None):
    # Пункт 6: filter()
    products = Product.objects.filter(stock_quantity__gt=0).select_related('category')
    category_name = request.GET.get('category_name')
    if category_name:
        products = products.filter(category__name__icontains=category_name)
    category = None
    if category_slug:
        # Пункт 11: get_object_or_404
        category = get_object_or_404(Category, slug=category_slug) #если категории нет - покажет страницу с ошибкой 404

        products = products.filter(category=category)

    silver_type = request.GET.get('silver_type')
    if silver_type:
        products = products.filter(silver_type=silver_type)
    
    # Пункт 8: exclude() убираем те товары, у которых олд прайс не пустой и олд прайс больше текущей цены
    no_discount = request.GET.get('no_discount')
    if no_discount:
        products = products.exclude(old_price__isnull=False, old_price__gt=0)
    
    # Пункт 9: order_by()
    sort_by = request.GET.get('sort', '-created_at') #Смотрим в URL параметр sort. Если его нет — сортируем по новизне (-created_at)
    products = products.order_by(sort_by) #Сортируем товары по тому полю, которое пришло в параметре sort
    
    # Пункт 14: пагинация + try except
    paginator = Paginator(products, 12) #12 товаров на страницу
    page = request.GET.get('page', 1) #получаем номер страницы из URL
    try:
        #достает нужную страницу
        products_page = paginator.page(page)
    except PageNotAnInteger:
        # Если ввели буквы (?page=abc) — показываем первую страницу
        products_page = paginator.page(1)
    except EmptyPage:
        # Если страницы нет (?page=999) — показываем последнюю
        products_page = paginator.page(paginator.num_pages)
    
    # Пункт 15: агрегация Считает статистику по ВСЕМ записям
    stats = Product.objects.aggregate(
        avg_price=Avg('price'),
        total_products=Count('id')
    )
    
    return render(request, 'store/product_list.html', {
        'products': products_page,
        'category': category,
        'stats': stats,
    })

# Пункт 11,13: get_object_or_404, get_absolute_url
def product_detail(request, product_id, slug=None):
    product = get_object_or_404(
        Product.objects.select_related('category', 'created_by'),
        id=product_id
    ) #если товара нет - страница 404
    return render(request, 'store/product_detail.html', {'product': product})

# Пункт 19: аутентификация
def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.first_name}!')
            return redirect('store:product_list')
    else:
        form = UserRegistrationForm()
    return render(request, 'store/register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'С возвращением, {user.email}!')
            return redirect('store:product_list')
    else:
        form = UserLoginForm()
    return render(request, 'store/login.html', {'form': form})

def user_logout(request):
    logout(request)
    messages.info(request, 'Вы вышли из системы')
    return redirect('store:product_list')

@login_required
def profile(request):
    user_orders = Order.objects.filter(user=request.user).prefetch_related( #все заказы текущего пользователя
        'items',           # все позиции заказа для этих заказов, обратная связь к OrderItem
        'items__product'   # все товары для этих позиций, через OrderItem к Product
    ).order_by('-created_at')
    
    return render(request, 'store/profile.html', {
        'user': request.user,
        'orders': user_orders
    })


from .forms import ProductForm, ReviewForm

from django.core.exceptions import PermissionDenied  # добавить в импорты

# Создание товара (только для персонала)
@login_required
def product_create(request):
    if not request.user.is_staff:
        raise PermissionDenied("Доступ запрещён. Только для администраторов.")
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.created_by = request.user
            product.save()
            if not product.slug:
                from django.utils.text import slugify
                product.slug = slugify(product.name)
                product.save()
            product.refresh_from_db()
            messages.success(request, f'Товар "{product.name}" создан!')
            return redirect('store:product_detail', product_id=product.id, slug=product.slug)
    else:
        form = ProductForm()
    return render(request, 'store/product_form.html', {'form': form, 'title': 'Добавить товар'})

# Редактирование товара (только для персонала)
@login_required
def product_edit(request, product_id):
    print("=== product_edit ВЫЗВАНА ===")  # ← добавить
    print(f"product_id = {product_id}")     # ← добавить
    print(f"method = {request.method}")  
    if not request.user.is_staff:
        raise PermissionDenied("Доступ запрещён. Только для администраторов.")
    
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f'Товар "{product.name}" обновлён!')
            return redirect('store:product_detail', product_id=product.id, slug=product.slug)
    else:
        form = ProductForm(instance=product)
    
    # ВАЖНО: этот render должен выполняться для GET-запроса
    return render(request, 'store/product_form.html', {'form': form, 'title': 'Редактировать товар'})

# Удаление товара (только для персонала)
@login_required
def product_delete(request, product_id):
    if not request.user.is_staff:
        raise PermissionDenied("Доступ запрещён. Только для администраторов.")
    
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        product_name = product.name
        product.delete()
        messages.success(request, f'Товар "{product_name}" удалён!')
        return redirect('store:product_list')
    return render(request, 'store/product_confirm_delete.html', {'product': product})

# Добавление товара в корзину
@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # Получаем или создаём корзину пользователя
    cart, created = Cart.objects.get_or_create(user=request.user)
    
    # Получаем или создаём позицию в корзине
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1}
    )
    
    # Если позиция уже была, увеличиваем количество
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    
    messages.success(request, f'Товар "{product.name}" добавлен в корзину')
    return redirect('store:cart_detail')

# Удаление товара из корзины
@login_required
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    product_name = cart_item.product.name
    cart_item.delete()
    
    messages.success(request, f'Товар "{product_name}" удалён из корзины')
    return redirect('store:cart_detail')

# Изменение количества товара в корзине
@login_required
def update_cart_quantity(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
        else:
            cart_item.delete()
    
    return redirect('store:cart_detail')

def cart_detail(request):
    """Корзина пользователя"""
    cart = Cart.objects.get(user=request.user)
    items = cart.items.select_related('product', 'product__category')
    return render(request, 'store/cart.html', {'cart': cart, 'items': items})

# Оформление заказа
@login_required
def checkout(request):
    cart = Cart.objects.get(user=request.user)
    items = cart.items.all()
    
    if not items:
        messages.warning(request, 'Корзина пуста')
        return redirect('store:cart_detail')
    
    if request.method == 'POST':
        # Создаём заказ
        order = Order.objects.create(
            user=request.user,
            delivery_address=request.POST.get('delivery_address'),
            delivery_method=request.POST.get('delivery_method'),
            payment_method=request.POST.get('payment_method'),
            gift_wrap=request.POST.get('gift_wrap') == 'on',
            gift_message=request.POST.get('gift_message', ''),
            comment=request.POST.get('comment', '')
        )
        
        # Переносим товары из корзины в заказ
        for item in items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                product_name=item.product.name,
                price=item.product.price,
                quantity=item.quantity
            )
        
        # Очищаем корзину
        items.delete()
        
        messages.success(request, f'Заказ #{order.order_number} оформлен!')
        return redirect('store:order_detail', order_number=order.order_number)
    
    return render(request, 'store/checkout.html', {
        'cart': cart,
        'items': items,
        'delivery_methods': Order.DELIVERY_CHOICES,
        'payment_methods': Order.PAYMENT_CHOICES,
    })

# Просмотр заказа
@login_required
def order_detail(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    return render(request, 'store/order_detail.html', {'order': order})

# Список заказов пользователя
@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'store/my_orders.html', {'orders': orders})
