from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Sum, Avg, Count, Q
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.http import HttpResponseRedirect
from .models import Product, Category, User, Order
from .forms import UserRegistrationForm, UserLoginForm

def product_list(request, category_slug=None):
    # Пункт 6: filter()
    products = Product.objects.filter(stock_quantity__gt=0)
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
    product = get_object_or_404(Product, id=product_id) #если товара нет - страница 404
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
    """Личный кабинет (доступен только авторизованным)"""
    user_orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'store/profile.html', {
        'user': request.user,
        'orders': user_orders
    })
