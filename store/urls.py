from django.urls import path
from . import views
app_name = 'store'
urlpatterns = [
    # Главная
    path('', views.product_list, name='product_list'),
    path('category/<slug:category_slug>/', views.product_list, name='category'),
    
    # 👇 КОНКРЕТНЫЕ МАРШРУТЫ ДОЛЖНЫ БЫТЬ ПЕРВЫМИ 👇
    path('product/create/', views.product_create, name='product_create'),
    path('product/<int:product_id>/edit/', views.product_edit, name='product_edit'),
    path('product/<int:product_id>/delete/', views.product_delete, name='product_delete'),
    
    # 👇 ОБЩИЙ МАРШРУТ (с slug) ДОЛЖЕН БЫТЬ ПОСЛЕДНИМ 👇
    path('product/<int:product_id>/<slug:slug>/', views.product_detail, name='product_detail'),
    
    # Корзина
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_quantity, name='update_cart_quantity'),
    
    # Оформление заказа
    path('checkout/', views.checkout, name='checkout'),
    path('order/<str:order_number>/', views.order_detail, name='order_detail'),
    path('my-orders/', views.my_orders, name='my_orders'),
    
    # Аутентификация
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
]