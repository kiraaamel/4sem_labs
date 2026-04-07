from decimal import Decimal
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    User, Category, Product, Cart, CartItem, 
    Order, OrderItem, Review, Wishlist
)
from .admin_actions import export_products_to_pdf

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'email', 'get_full_name', 'phone', 'bonus_points', 
                   'is_active', 'is_staff', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'date_joined']
    list_display_links = ['email']
    search_fields = ['email', 'first_name', 'last_name', 'phone']
    readonly_fields = ['date_joined', 'last_login']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('email', 'first_name', 'last_name', 'phone', 'bonus_points')
        }),
        ('Права доступа', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Важные даты', {
            'fields': ('date_joined', 'last_login')
        }),
    )
    
    filter_horizontal = ['groups', 'user_permissions']
    
    @admin.display(description='Полное имя')
    def get_full_name(self, obj):
        return obj.get_full_name() or '-'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'slug', 'parent', 'has_children', 'products_count']
    list_filter = ['parent']
    list_display_links = ['name']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['id']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'slug', 'parent', 'description')
        }),
        ('Изображение', {
            'fields': ('image',),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(boolean=True, description='Есть подкатегории')
    def has_children(self, obj):
        return obj.children.exists()
    
    @admin.display(description='Количество товаров')
    def products_count(self, obj):
        count = obj.products.count()
        url = reverse('admin:store_product_changelist') + f'?category__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1
    raw_id_fields = ['product']
    readonly_fields = ['added_at', 'total_price_display']
    
    @admin.display(description='Общая сумма')
    def total_price_display(self, obj):
        return f"{obj.total_price} ₽"


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'user_display', 'total_items', 'total_price_display', 
                   'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__email', 'session_key']
    readonly_fields = ['created_at', 'updated_at', 'total_price_display']
    raw_id_fields = ['user']
    inlines = [CartItemInline]
    
    @admin.display(description='Пользователь')
    def user_display(self, obj):
        if obj.user:
            return obj.user.email
        return f"Гость: {obj.session_key}"
    
    @admin.display(description='Общая сумма')
    def total_price_display(self, obj):
        return f"{obj.total_price} ₽"
    
    @admin.display(description='Количество товаров')
    def total_items(self, obj):
        return obj.total_items


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    raw_id_fields = ['product']
    readonly_fields = ['total_price_display']
    fields = ['product', 'quantity']
    
    @admin.display(description='Сумма')
    def total_price_display(self, obj):
        return f"{obj.total_price} ₽"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'user_display', 'created_at', 'status', 
                   'total_price_display', 'delivery_method', 'payment_method']
    list_filter = ['status', 'delivery_method', 'payment_method', 'created_at', 'gift_wrap']
    list_display_links = ['order_number']
    search_fields = ['order_number', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['order_number', 'created_at', 'total_price_display', 'delivered_at']
    date_hierarchy = 'created_at'
    raw_id_fields = ['user']
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('Информация о заказе', {
            'fields': ('order_number', 'user', 'status', 'total_price_display', 'created_at')
        }),
        ('Доставка и оплата', {
            'fields': ('delivery_address', 'delivery_method', 'payment_method')
        }),
        ('Подарочная упаковка', {
            'fields': ('gift_wrap', 'gift_message'),
            'classes': ('collapse',)
        }),
        ('Дополнительно', {
            'fields': ('comment', 'delivered_at')
        }),
    )
    
    @admin.display(description='Пользователь')
    def user_display(self, obj):
        if obj.user:
            return obj.user.email
        return 'Гость'
    
    @admin.display(description='Сумма заказа')
    def total_price_display(self, obj):
        return format_html('<b>{} ₽</b>', obj.total_price)
    
    actions = ['mark_as_confirmed', 'mark_as_shipped', 'mark_as_delivered']
    
    @admin.action(description='Подтвердить выбранные заказы')
    def mark_as_confirmed(self, request, queryset):
        updated = queryset.update(status='confirmed')
        self.message_user(request, f'Подтверждено заказов: {updated}')
    
    @admin.action(description='Отправить выбранные заказы')
    def mark_as_shipped(self, request, queryset):
        updated = queryset.update(status='shipped')
        self.message_user(request, f'Отправлено заказов: {updated}')
    
    @admin.action(description='Отметить как доставленные')
    def mark_as_delivered(self, request, queryset):
        updated = queryset.update(status='delivered', delivered_at=timezone.now())
        self.message_user(request, f'Доставлено заказов: {updated}')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'category', 'price_display', 
                   'silver_info', 'weight', 'stock_status', 'has_discount_display', 
                   'stones_display', 'image_preview', 'images_count_display', 'created_at', 'instruction_file_link']
    list_filter = ['category', 'silver_type', 'fineness', 'stones', 'created_at', 'collection']
    list_display_links = ['name']
    search_fields = ['name', 'description', 'collection']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at', 'available_quantity_display', 
                      'full_silver_info', 'images_preview']
    raw_id_fields = ['created_by', 'category']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'slug', 'description', 'category')
        }),
        ('Цены', {
            'fields': ('price', 'old_price'),
            'classes': ('wide',)
        }),
        ('Остатки на складе', {
            'fields': ('stock_quantity', 'reserved_quantity', 'available_quantity_display'),
            'classes': ('wide',)
        }),
        ('Фотографии товара', {
            'fields': ('image', 'image_2', 'image_3', 'image_4', 'image_5', 'images_preview'),
            'description': 'Загрузите фотографии товара. Первое фото (Главное) обязательно для отображения',
            'classes': ('wide',)
        }),
        ('Характеристики серебра', {
            'fields': ('silver_type', 'fineness', 'weight', 'size', 'full_silver_info'),
            'description': 'Информация о типе и пробе серебряного изделия'
        }),
        ('Драгоценные камни', {
            'fields': ('stones', 'stone_type', 'stone_weight'),
            'classes': ('collapse',),
            'description': 'Если в изделии есть камни, укажите их характеристики'
        }),
        ('Документы', {
            'fields': ('instruction_file',),
            'classes': ('collapse',),
            'description': 'Загрузите дополнительные файлы (инструкции, сертификаты)'
        }),
        ('Ссылки', { 
            'fields': ('external_link',),
            'classes': ('collapse',),
            'description': 'Ссылка на видеообзор, сайт производителя или дополнительную информацию'
        }),
        ('Метаданные', {
            'fields': ('collection', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Цена')
    def price_display(self, obj):
        if obj.has_discount:
            discount_percent = int((obj.old_price - obj.price) / obj.old_price * 100)
            return format_html(
                '<span style="color: red; font-weight: bold;">{} ₽</span> '
                '<del style="color: gray;">{} ₽</del> '
                '<span style="color: green;">(-{}%)</span>',
                obj.price, obj.old_price, discount_percent
            )
        return format_html('<span style="font-weight: bold;">{} ₽</span>', obj.price)
    @admin.display(description='Инструкция')
    def instruction_file_link(self, obj):
        if obj.instruction_file:
            return format_html('<a href="{}" target="_blank">📄 Скачать инструкцию</a>', obj.instruction_file.url)
        return '-'
    
    @admin.display(description='Ссылка')
    def external_link(self, obj):
        if obj.external_link:
            return format_html('<a href="{}" target="_blank">🔗 Открыть</a>', obj.external_link)
        return '-'

    @admin.display(description='Серебро')
    def silver_info(self, obj):
        silver_type_display = obj.get_silver_type_display()
        fineness_display = obj.get_fineness_display()
        
        color = '#666'
        if 'sterling' in obj.silver_type:
            color = '#2c3e50'
        elif 'oxidized' in obj.silver_type:
            color = '#34495e'
        elif 'rhodium' in obj.silver_type:
            color = '#7f8c8d'
        elif 'black' in obj.silver_type:
            color = '#2c3e50'
            
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span><br>'
            '<span style="color: gray; font-size: 0.9em;">{}</span>',
            color, silver_type_display, fineness_display
        )
    
    @admin.display(description='Полное описание')
    def full_silver_info(self, obj):
        return format_html(
            '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
            '<strong>Тип:</strong> {}<br>'
            '<strong>Проба:</strong> {}<br>'
            '<strong>Вес:</strong> {} г<br>'
            '<strong>Размер:</strong> {}</div>',
            obj.get_silver_type_display(),
            obj.get_fineness_display(),
            obj.weight,
            obj.size or 'Не указан'
        )
    
    @admin.display(description='Превью фото')
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 50px; border-radius: 5px;" />',
                obj.image.url
            )
        return '-'
    
    @admin.display(description='Все фото')
    def images_preview(self, obj):
        images_html = '<div style="display: flex; gap: 10px; flex-wrap: wrap;">'
        if obj.image:
            images_html += format_html(
                '<div><img src="{}" style="max-height: 100px; max-width: 100px; border-radius: 5px;" /><br><small>Главное</small></div>',
                obj.image.url
            )
        if obj.image_2:
            images_html += format_html(
                '<div><img src="{}" style="max-height: 100px; max-width: 100px; border-radius: 5px;" /></div>',
                obj.image_2.url
            )
        if obj.image_3:
            images_html += format_html(
                '<div><img src="{}" style="max-height: 100px; max-width: 100px; border-radius: 5px;" /></div>',
                obj.image_3.url
            )
        if obj.image_4:
            images_html += format_html(
                '<div><img src="{}" style="max-height: 100px; max-width: 100px; border-radius: 5px;" /></div>',
                obj.image_4.url
            )
        if obj.image_5:
            images_html += format_html(
                '<div><img src="{}" style="max-height: 100px; max-width: 100px; border-radius: 5px;" /></div>',
                obj.image_5.url
            )
        images_html += '</div>'
        
        if obj.images_count == 0:
            return 'Нет фотографий'
        return format_html(images_html)
    
    @admin.display(description='Кол-во фото')
    def images_count_display(self, obj):
        count = obj.images_count
        if count == 0:
            return format_html('<span style="color: red;">0</span>')
        elif count == 1:
            return format_html('<span style="color: orange;">{} (нет доп.)</span>', count)
        else:
            return format_html('<span style="color: green;">{} ({} доп.)</span>', count, count - 1)
    
    @admin.display(description='Доступно')
    def available_quantity_display(self, obj):
        available = obj.available_quantity
        if available <= 0:
            return format_html('<span style="color: red; font-weight: bold;">Нет в наличии</span>')
        elif available < 10:
            return format_html('<span style="color: orange; font-weight: bold;">Осталось {} шт</span>', available)
        elif available < 50:
            return format_html('<span style="color: green;">В наличии {} шт</span>', available)
        else:
            return format_html('<span style="color: blue;">В наличии {} шт</span>', available)
    
    @admin.display(boolean=True, description='Скидка')
    def has_discount_display(self, obj):
        return obj.has_discount
    
    @admin.display(description='Статус')
    def stock_status(self, obj):
        available = obj.available_quantity
        if available <= 0:
            return 'Нет в наличии'
        elif available < 10:
            return 'Мало'
        return 'В наличии'
    
    @admin.display(description='Камни')
    def stones_display(self, obj):
        if not obj.stones:
            return 'Без камней'
        
        stone_display = obj.get_stone_type_display()
        if obj.stone_weight:
            return f"{stone_display} ({obj.stone_weight} кар)"
        return stone_display
    
    @admin.action(description='Применить скидку 10 процентов к выбранным товарам')
    def apply_discount(self, request, queryset):
        for product in queryset:
            if not product.old_price:
                product.old_price = product.price
            product.price = product.price * Decimal('0.9')
            product.save()
        self.message_user(request, f'Скидка применена к {queryset.count()} товарам')
    
    @admin.action(description='Увеличить цену на 5 процентов')
    def increase_price(self, request, queryset):
        for product in queryset:
            product.price = product.price * Decimal('1.05')
            product.save()
        self.message_user(request, f'Цена увеличена для {queryset.count()} товаров')
    
    actions = [apply_discount, increase_price, export_products_to_pdf]

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'cart', 'product', 'quantity', 'total_price_display', 'added_at']
    list_filter = ['added_at']
    search_fields = ['cart__user__email', 'product__name']
    raw_id_fields = ['cart', 'product']
    readonly_fields = ['total_price_display']
    
    @admin.display(description='Общая сумма')
    def total_price_display(self, obj):
        return f"{obj.total_price} ₽"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'product_name', 'price', 'quantity', 'total_price_display']
    list_filter = ['order__status']
    search_fields = ['order__order_number', 'product_name']
    raw_id_fields = ['order', 'product']
    readonly_fields = ['total_price_display', 'product_name', 'price']
    
    fieldsets = (
        ('Информация о заказе', {
            'fields': ('order', 'product')
        }),
        ('Детали товара', {
            'fields': ('product_name', 'price', 'quantity')
        }),
    )
    
    @admin.display(description='Общая сумма')
    def total_price_display(self, obj):
        return f"{obj.total_price} ₽"
    
    def save_model(self, request, obj, form, change):
        """При сохранении автоматически заполняем product_name и price"""
        if obj.product:
            if not obj.product_name:
                obj.product_name = obj.product.name
            if not obj.price:
                obj.price = obj.product.price
        super().save_model(request, obj, form, change)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'product', 'rating_stars', 'comment_preview', 
                   'created_at', 'moderated']
    list_filter = ['rating', 'moderated', 'created_at']
    list_display_links = ['user']
    search_fields = ['user__email', 'product__name', 'comment']
    readonly_fields = ['created_at']
    raw_id_fields = ['user', 'product']
    list_editable = ['moderated']
    
    fieldsets = (
        ('Информация об отзыве', {
            'fields': ('user', 'product', 'rating', 'comment', 'image')
        }),
        ('Модерация', {
            'fields': ('moderated', 'created_at')
        }),
    )
    
    @admin.display(description='Оценка')
    def rating_stars(self, obj):
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        return format_html('<span style="color: gold;">{}</span>', stars)
    
    @admin.display(description='Отзыв')
    def comment_preview(self, obj):
        return obj.comment[:100] + '...' if len(obj.comment) > 100 else obj.comment
    
    actions = ['approve_reviews']
    
    @admin.action(description='Одобрить выбранные отзывы')
    def approve_reviews(self, request, queryset):
        updated = queryset.update(moderated=True)
        self.message_user(request, f'Одобрено отзывов: {updated}')


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'product', 'added_at']
    list_filter = ['added_at']
    search_fields = ['user__email', 'product__name']
    readonly_fields = ['added_at']
    raw_id_fields = ['user', 'product']
    
    fieldsets = (
        ('Избранное', {
            'fields': ('user', 'product', 'added_at')
        }),
    )