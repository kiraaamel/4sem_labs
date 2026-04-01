from django.contrib import admin
from .models import (
    User, Category, Product, 
    Cart, CartItem, Order, OrderItem, Review, Wishlist
)


class OrderItemInline(admin.TabularInline):
    """
    Встроенная форма для позиций заказа.
    """
    model = OrderItem
    extra = 1
    fields = ['product', 'quantity', 'item_total_display']
    readonly_fields = ['item_total_display']
    
    @admin.display(description='Стоимость')
    def item_total_display(self, obj):
        """
        Рассчитывает стоимость позиции.
        """
        if obj.pk and obj.product and obj.quantity:
            total = obj.product.price * obj.quantity
            return f"{total} ₽"
        elif obj.pk and obj.price and obj.quantity:
            total = obj.price * obj.quantity
            return f"{total} ₽"
        return "0 ₽"


class CartItemInline(admin.TabularInline):
    """
    Встроенная форма для элементов корзины.
    """
    model = CartItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'added_at', 'total_price']


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """
    Настройки отображения пользователя в админке.
    """
    list_display = ['email', 'first_name', 'last_name', 'phone', 'bonus_points', 'is_staff', 'is_active']
    list_filter = ['is_staff', 'is_active', 'date_joined']
    search_fields = ['email', 'first_name', 'last_name', 'phone']
    readonly_fields = ['last_login', 'date_joined']
    
    fieldsets = (
        ('Личная информация', {
            'fields': ('email', 'first_name', 'last_name', 'phone', 'bonus_points')
        }),
        ('Права доступа', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Важные даты', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Полное имя')
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """
    Настройки отображения категорий в админке.
    """
    list_display = ['name', 'slug', 'parent']
    list_filter = ['parent']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    
    @admin.display(description='Количество товаров')
    def products_count(self, obj):
        return obj.products.count()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """
    Настройки отображения товара в админке.
    """
    list_display = ['name', 'price', 'stock_quantity', 'category', 'metal', 'stones', 'created_at']
    list_filter = ['category', 'metal', 'stones', 'created_at']
    search_fields = ['name', 'description', 'collection']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'slug', 'description', 'category')
        }),
        ('Цены и наличие', {
            'fields': ('price', 'old_price', 'stock_quantity', 'reserved_quantity')
        }),
        ('Характеристики', {
            'fields': ('metal', 'fineness', 'weight', 'size', 'stones', 'stone_type', 'collection')
        }),
        ('Изображение', {
            'fields': ('image',)
        }),
        ('Мета-информация', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Доступно')
    def available_quantity(self, obj):
        return obj.stock_quantity - obj.reserved_quantity
    
    @admin.display(description='Рейтинг')
    def average_rating(self, obj):
        reviews = obj.reviews.filter(moderated=True)
        if not reviews:
            return 0
        total = sum(review.rating for review in reviews)
        return round(total / reviews.count(), 1)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """
    Настройки отображения корзины в админке.
    """
    inlines = [CartItemInline]
    list_display = ['id', 'user', 'session_key', 'total_items', 'total_price', 'updated_at']
    list_filter = ['updated_at']
    search_fields = ['user__email', 'session_key']
    readonly_fields = ['created_at', 'updated_at']
    
    @admin.display(description='Всего товаров')
    def total_items(self, obj):
        return sum(item.quantity for item in obj.items.all())
    
    @admin.display(description='Общая стоимость')
    def total_price(self, obj):
        return sum(item.product.price * item.quantity for item in obj.items.all())


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Настройки отображения заказа в админке.
    """
    inlines = [OrderItemInline]
    list_display = ['order_number', 'user', 'created_at', 'status', 'total_price', 'delivery_method']
    list_filter = ['status', 'delivery_method', 'payment_method', 'created_at']
    search_fields = ['order_number', 'user__email', 'delivery_address']
    readonly_fields = ['order_number', 'created_at']
    list_editable = ['status']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('order_number', 'user', 'status', 'created_at')
        }),
        ('Доставка', {
            'fields': ('delivery_address', 'delivery_method', 'delivered_at')
        }),
        ('Оплата', {
            'fields': ('payment_method',)
        }),
        ('Дополнительно', {
            'fields': ('gift_wrap', 'gift_message', 'comment'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Общая стоимость')
    def total_price(self, obj):
        total = 0
        for item in obj.items.all():
            if item.product and item.quantity:
                total += item.product.price * item.quantity
            elif item.price and item.quantity:
                total += item.price * item.quantity
        return f"{total} ₽"
    
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        
        order = form.instance
        for item in order.items.all():
            if item.product:
                if not item.product_name or item.product_name != item.product.name:
                    item.product_name = item.product.name
                if not item.price or item.price != item.product.price:
                    item.price = item.product.price
                item.save()


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """
    Настройки отображения отзывов в админке.
    """
    list_display = ['id', 'user', 'product', 'rating', 'created_at', 'moderated']
    list_filter = ['rating', 'moderated', 'created_at']
    search_fields = ['user__email', 'product__name', 'comment']
    list_editable = ['moderated']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'product', 'rating', 'created_at')
        }),
        ('Содержание', {
            'fields': ('comment', 'image')
        }),
        ('Модерация', {
            'fields': ('moderated',)
        }),
    )
    
    @admin.display(description='Оценка звездами')
    def rating_stars(self, obj):
        return "★" * obj.rating + "☆" * (5 - obj.rating)


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    """
    Настройки отображения избранного в админке.
    """
    list_display = ['id', 'user', 'product', 'added_at']
    list_filter = ['added_at']
    search_fields = ['user__email', 'product__name']
    readonly_fields = ['added_at']


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    """
    Настройки отображения элементов корзины в админке.
    """
    list_display = ['id', 'cart', 'product', 'quantity', 'added_at']
    list_filter = ['added_at']
    search_fields = ['cart__user__email', 'product__name']
    readonly_fields = ['added_at']


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """
    Настройки отображения позиций заказа в админке.
    """
    list_display = ['id', 'order', 'product_name', 'price', 'quantity']
    list_filter = ['order__status']
    search_fields = ['order__order_number', 'product_name']
    readonly_fields = ['total_price']
    
    @admin.display(description='Общая стоимость')
    def total_price(self, obj):
        return obj.price * obj.quantity