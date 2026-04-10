from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Sum, Avg, Count, Q, F
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.http import HttpResponseRedirect
from .models import Product, Category, User, Order, Cart, CartItem, OrderItem, Review
from .forms import UserRegistrationForm, UserLoginForm, ProductForm, ReviewForm

def get_cart(request):
    """Получение корзины для пользователя или гостя (через сессию)"""
    if request.user.is_authenticated:
        # Авторизованный пользователь
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        # Гость — используем сессию
        session_key = request.session.session_key #Уникальный ключ сессии для этого браузера
        if not session_key:
            request.session.create() #создание новой сессии, если её нет
            session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key, user=None) #cоздание корзины для гостя
    return cart

def product_list(request):
    """Главная страница с новинками и популярными категориями/типами серебра"""
    
    # 5 последних новинок для блока "Новинки"
    top_5_new = Product.objects.filter(stock_quantity__gt=0).order_by('-created_at')[:5] #ограничения кол-ва (Пункт 4)
    
    # Пункт 5: values() - для быстрого получения данных (используем для списка категорий)
    categories_list = Category.objects.values('id', 'name', 'slug')[:6] #возвращает список словарей с указанными полями
    
    # Пункт 5: values_list() - для простого списка (используем для типов серебра)
    popular_silver_types = Product.objects.values_list('silver_type', flat=True).distinct()[:4] #возвращает список кортежей
    
    # Пункт 6: count() и exists()
    total_products = Product.objects.count() #кол-во записей
    has_products = Product.objects.exists() #проверка есть ли хотя бы одна запись
    has_discounted_products = Product.objects.filter(old_price__isnull=False, old_price__gt=F('price')).exists()
    in_stock_count = Product.objects.filter(stock_quantity__gt=0).count()
    
    # Пункт 15: агрегация Считает статистику по ВСЕМ записям
    stats = Product.objects.aggregate(
        avg_price=Avg('price'),
        total_products=Count('id')
    )
    
    return render(request, 'store/product_list.html', {
        'top_5_new': top_5_new,
        'categories_list': categories_list,
        'popular_silver_types': popular_silver_types,
        'total_products': total_products,
        'has_products': has_products,
        'has_discounted_products': has_discounted_products,
        'in_stock_count': in_stock_count,
        'stats': stats,
    })

def catalog(request):
    """Страница каталога с фильтрацией и сортировкой"""
    # Пункт 6: filter() чтобы уточнить поиск применением нескольких фильтров сразу
    products = Product.objects.filter(stock_quantity__gt=0).select_related('category')
    # __icontains (поиск по части слова, без учёта регистра) =====
    search_query = request.GET.get('search')
    if search_query:
        products = products.filter(name__icontains=search_query)  # поиск в названии
    #ЦЕПОЧКА ФИЛЬТРОВ
    # Все эти фильтры применяются последовательно (это и есть цепочка)
    category_slug = request.GET.get('category')
    if category_slug:
        products = products.filter(category__slug=category_slug)
    
    silver_type = request.GET.get('silver_type')
    if silver_type:
        products = products.filter(silver_type=silver_type)
    
    # Фильтр по цене
    min_price = request.GET.get('min_price')
    if min_price:
        products = products.filter(price__gte=min_price)
    
    max_price = request.GET.get('max_price')
    if max_price:
        products = products.filter(price__lte=max_price)
    
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
    
    # Список категорий для фильтра
    categories = Category.objects.all()
    
    # Типы серебра для фильтра
    silver_types = Product.SILVER_TYPE_CHOICES
    
    return render(request, 'store/catalog.html', {
        'products': products_page,
        'categories': categories,
        'silver_types': silver_types,
        'current_category': category_slug,
        'current_silver_type': silver_type,
        'current_min_price': min_price,
        'current_max_price': max_price,
        'current_no_discount': no_discount,
        'current_sort': sort_by,
        'search_query': search_query,
    })

# Пункт 11,13: get_object_or_404, get_absolute_url
def product_detail(request, product_id, slug=None):
    product = get_object_or_404(
        Product.objects.select_related('category', 'created_by'),
        id=product_id
    ) #если товара нет - страница 404
    
    # Логика для отзывов
    if request.method == 'POST':
        form = ReviewForm(request.POST, request.FILES) #словарь с загруженными файлами
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.product = product
            review.save()
            messages.success(request, 'Спасибо за ваш отзыв!')
            return redirect('store:product_detail', product_id=product.id, slug=product.slug) #перенаправление на детальную страницу товара
    else:
        form = ReviewForm()
    
    return render(request, 'store/product_detail.html', {
        'product': product,
        'review_form': form
    })

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid(): #проверяет прошла ли форма валидацию
            email = form.cleaned_data.get('email') #приводит данные к норм виду, в данном случае к нижнему регистру
            user = form.save()
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.first_name}!')
            return redirect('store:product_list') #перенаправление на главную страницу
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
from django.core.exceptions import PermissionDenied

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

def add_to_cart(request, product_id):
    """Добавление товара в корзину (работает и для гостей)"""
    product = get_object_or_404(Product, id=product_id)
    cart = get_cart(request)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1}
    )
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    messages.success(request, f'Товар "{product.name}" добавлен в корзину')
    return redirect('store:cart_detail')

def remove_from_cart(request, item_id):
    """Удаление товара из корзины (работает и для гостей)"""
    # Получаем корзину текущего пользователя/гостя
    cart = get_cart(request)
    # Ищем товар в этой корзине по id
    cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
    product_name = cart_item.product.name
    cart_item.delete()
    messages.success(request, f'Товар "{product_name}" удалён из корзины')
    return redirect('store:cart_detail')

def update_cart_quantity(request, item_id):
    """Изменение количества товара в корзине (работает и для гостей)"""
    cart = get_cart(request)
    cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        product = cart_item.product
        
        if action == 'increase':
            new_quantity = cart_item.quantity + 1
            # Проверка на доступное количество в БД
            if new_quantity <= product.available_quantity:
                cart_item.quantity = new_quantity
                cart_item.save()
            else:
                messages.warning(request, f'Доступно только {product.available_quantity} шт. товара "{product.name}"')
        
        elif action == 'decrease':
            new_quantity = cart_item.quantity - 1
            if new_quantity >= 1:
                cart_item.quantity = new_quantity
                cart_item.save()
            else:
                cart_item.delete()
                messages.success(request, f'Товар "{product.name}" удалён из корзины')
        
        else:
            # Обычное обновление через поле ввода
            quantity = int(request.POST.get('quantity', 1))
            if quantity > 0:
                if quantity <= product.available_quantity:
                    cart_item.quantity = quantity
                    cart_item.save()
                else:
                    messages.warning(request, f'Доступно только {product.available_quantity} шт. товара "{product.name}"')
            else:
                cart_item.delete()
    
    return redirect('store:cart_detail')

def cart_detail(request):
    """Корзина пользователя (работает и для гостей)"""
    cart = get_cart(request)
    items = cart.items.select_related('product', 'product__category')
    return render(request, 'store/cart.html', {'cart': cart, 'items': items})

@login_required
def checkout(request):
    """Оформление заказа (только для авторизованных пользователей)"""
    cart = get_cart(request)
    
    if cart.user != request.user:
        messages.error(request, 'Доступ запрещён. Корзина не принадлежит вам.')
        return redirect('store:cart_detail')
    
    items = cart.items.all()
    
    if not items:
        messages.warning(request, 'Корзина пуста')
        return redirect('store:cart_detail')
    
    # ПРОВЕРКА: хватает ли товаров на складе
    for item in items:
        if item.quantity > item.product.available_quantity:
            messages.error(request, f'Товара "{item.product.name}" осталось только {item.product.available_quantity} шт.')
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
        
        # Переносим товары из корзины в заказ И уменьшаем остатки
        for item in items:
            # Создаём позицию заказа
            OrderItem.objects.create(
                order=order,
                product=item.product,
                product_name=item.product.name,
                price=item.product.price,
                quantity=item.quantity
            )
            
            # УМЕНЬШАЕМ КОЛИЧЕСТВО НА СКЛАДЕ
            product = item.product
            product.stock_quantity -= item.quantity
            product.save()
        
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