import re
from decimal import Decimal
import uuid
import os
from django.urls import reverse
from django.db import models
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.base_user import BaseUserManager
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.core.validators import FileExtensionValidator

class AvailableProductManager(models.Manager):
    """Кастомный менеджер для товаров в наличии"""
    
    def get_queryset(self):
        """Возвращает только товары, у которых есть остаток на складе"""
        return super().get_queryset().filter(stock_quantity__gt=0)
    
    def with_discount(self):
        """Товары в наличии со скидкой"""
        return self.get_queryset().filter(old_price__isnull=False, old_price__gt=0)
    
    def by_silver_type(self, silver_type):
        """Товары определённого типа серебра"""
        return self.get_queryset().filter(silver_type=silver_type)

def validate_phone_number(value):
    """
    Валидация номера телефона для российских номеров
    """
    cleaned = re.sub(r'[\s\(\)\-]', '', value)
    pattern = r'^(\+7|7|8)(\d{10})$'
    match = re.match(pattern, cleaned)
    
    if not match:
        raise ValidationError(
            _('Некорректный формат номера телефона. Используйте формат: +7XXXXXXXXXX, 8XXXXXXXXXX или 7XXXXXXXXXX'),
            code='invalid_phone'
        )
    
    prefix = match.group(1)
    number = match.group(2)
    return f'+7{number}'


def generate_order_number():
    """Генерация уникального номера заказа"""
    return f"{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def product_image_upload_path(instance, filename):
    """
    Формирует путь для загрузки изображения товара
    """
    ext = filename.split('.')[-1]
    # Генерируем уникальное имя файла
    filename = f"{uuid.uuid4().hex}.{ext}"
    # Возвращаем путь: products/{product_id}/{filename}
    return f"products/{instance.id}/{filename}"


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email обязателен')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        
        # Создаем корзину для пользователя
        Cart.objects.get_or_create(user=user)
        
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(
        unique=True, 
        verbose_name='Адрес электронной почты',
        error_messages={'unique': 'Пользователь с таким email уже существует'}
    )
    first_name = models.CharField(max_length=150, blank=True, verbose_name='Имя')
    last_name = models.CharField(max_length=150, blank=True, verbose_name='Фамилия')
    phone = models.CharField(
        max_length=20, 
        blank=True, 
        validators=[validate_phone_number],
        verbose_name='Номер телефона',
        help_text='Формат: +7XXXXXXXXXX, 8XXXXXXXXXX или 7XXXXXXXXXX'
    )
    bonus_points = models.IntegerField(default=0, verbose_name='Бонусные баллы')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    is_staff = models.BooleanField(default=False, verbose_name='Персонал')
    date_joined = models.DateTimeField(default=timezone.now, verbose_name='Дата регистрации')
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['-date_joined'] # User сортировка — новые сверху
    
    def __str__(self):
        "Метод, который определяет, как объект модели отображается в виде строки (user@example.com (Иван Иванов))"
        name_part = f"{self.first_name} {self.last_name}".strip()
        return f"{self.email} ({name_part})" if name_part else self.email
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_formatted_phone(self):
        """Возвращает отформатированный номер телефона"""
        if self.phone:
            cleaned = re.sub(r'[^\d+]', '', self.phone)
            if cleaned.startswith('+') and len(cleaned) == 12:
                return f"+{cleaned[1]} ({cleaned[2:5]}) {cleaned[5:8]}-{cleaned[8:10]}-{cleaned[10:12]}"
            elif len(cleaned) == 11:
                return f"+7 ({cleaned[1:4]}) {cleaned[4:7]}-{cleaned[7:9]}-{cleaned[9:11]}"
        return self.phone


class Category(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название')
    slug = models.SlugField(unique=True, verbose_name='URL идентификатор')
    description = models.TextField(blank=True, verbose_name='Описание')
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        blank=True, 
        null=True, 
        related_name='children',
        verbose_name='Родительская категория'
    )
    image = models.ImageField(
        upload_to='categories/', 
        blank=True, 
        null=True, 
        verbose_name='Изображение'
    )
    
    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name'] # Category сортировка — по алфавиту
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(models.Model):
    SILVER_TYPE_CHOICES = [
        ('sterling', 'Стерлинговое серебро (925)'),
        ('fine', 'Чистое серебро (999)'),
        ('argentium', 'Аргентиум серебро'),
        ('mexican', 'Мексиканское серебро'),
        ('oxidized', 'Оксидированное серебро'),
        ('rhodium_plated', 'Серебро с родиевым покрытием'),
        ('black', 'Черненое серебро'),
        ('matte', 'Матовое серебро'),
    ]
    
    FINENESS_CHOICES = [
        ('800', '800 проба'),
        ('830', '830 проба'),
        ('875', '875 проба'),
        ('900', '900 проба'),
        ('916', '916 проба'),
        ('925', '925 проба'),
        ('960', '960 проба'),
        ('999', '999 проба'),
    ]
    
    STONE_TYPE_CHOICES = [
        ('diamond', 'Бриллиант'),
        ('ruby', 'Рубин'),
        ('sapphire', 'Сапфир'),
        ('emerald', 'Изумруд'),
        ('topaz', 'Топаз'),
        ('amethyst', 'Аметист'),
        ('garnet', 'Гранат'),
        ('peridot', 'Перидот'),
        ('citrine', 'Цитрин'),
        ('aquamarine', 'Аквамарин'),
        ('tourmaline', 'Турмалин'),
        ('opal', 'Опал'),
        ('pearl', 'Жемчуг'),
        ('cubic_zirconia', 'Фианит'),
        ('moonstone', 'Лунный камень'),
        ('none', 'Нет камней'),
    ]
    
    name = models.CharField(max_length=200, verbose_name='Название')
    slug = models.SlugField(unique=True, verbose_name='URL идентификатор')
    description = models.TextField(verbose_name='Описание')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')
    old_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, 
        verbose_name='Старая цена'
    )
    stock_quantity = models.PositiveIntegerField(default=0, verbose_name='Количество на складе')
    reserved_quantity = models.PositiveIntegerField(default=0, verbose_name='Зарезервировано')
    category = models.ForeignKey(
        Category, 
        on_delete=models.CASCADE, 
        related_name='products', #задаем имя для всех товаров категории
        verbose_name='Категория'
    )
    
    # Поля для фотографий
    image = models.ImageField(
        upload_to=product_image_upload_path,
        blank=True,
        null=True,
        verbose_name='Главное фото',
        help_text='Основное фото товара (обязательно для отображения)'
    )
    image_2 = models.ImageField(
        upload_to=product_image_upload_path,
        blank=True,
        null=True,
        verbose_name='Дополнительное фото 2',
        help_text='Дополнительное фото товара'
    )
    image_3 = models.ImageField(
        upload_to=product_image_upload_path,
        blank=True,
        null=True,
        verbose_name='Дополнительное фото 3'
    )
    image_4 = models.ImageField(
        upload_to=product_image_upload_path,
        blank=True,
        null=True,
        verbose_name='Дополнительное фото 4'
    )
    image_5 = models.ImageField(
        upload_to=product_image_upload_path,
        blank=True,
        null=True,
        verbose_name='Дополнительное фото 5'
    )
    
    silver_type = models.CharField(
        max_length=30, 
        choices=SILVER_TYPE_CHOICES,
        default='sterling',
        verbose_name='Тип серебра'
    )
    fineness = models.CharField(
        max_length=4, 
        choices=FINENESS_CHOICES,
        default='925',
        verbose_name='Проба серебра'
    )
    
    weight = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        verbose_name='Вес изделия (г)'
    )
    size = models.CharField(
        max_length=20, 
        blank=True, 
        verbose_name='Размер (для колец, браслетов)',
        help_text='Например: 16.5, 17, 18, S, M, L'
    )
    
    stones = models.BooleanField(default=False, verbose_name='Наличие драгоценных камней')
    stone_type = models.CharField(
        max_length=20, 
        choices=STONE_TYPE_CHOICES, 
        blank=True, 
        verbose_name='Тип камня'
    )
    stone_weight = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        blank=True, 
        null=True,
        verbose_name='Вес камней (карат)',
        help_text='Общий вес всех камней в каратах'
    )
    
    collection = models.CharField(max_length=100, blank=True, verbose_name='Коллекция')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='created_products',
        verbose_name='Создал'
    )

    objects = models.Manager()              # стандартный менеджер (все товары)
    available = AvailableProductManager()  #кастомный менеджер (только в наличии)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['-created_at']  # Product сортировка — новые сверху
    
    def __str__(self):
        silver_display = self.get_silver_type_display()
        return f"{self.name} - {silver_display} ({self.get_fineness_display()}) - {self.price}₽"
    
    @property
    def available_quantity(self):
        return self.stock_quantity - self.reserved_quantity
    
    @property
    def has_discount(self):
        return self.old_price is not None and self.old_price > self.price
    
    @property
    def all_images(self):
        """Возвращает список всех загруженных изображений"""
        images = []
        if self.image:
            images.append(('main', self.image))
        if self.image_2:
            images.append(('2', self.image_2))
        if self.image_3:
            images.append(('3', self.image_3))
        if self.image_4:
            images.append(('4', self.image_4))
        if self.image_5:
            images.append(('5', self.image_5))
        return images
    
    @property
    def images_count(self):
        """Количество загруженных изображений"""
        count = 0
        if self.image:
            count += 1
        if self.image_2:
            count += 1
        if self.image_3:
            count += 1
        if self.image_4:
            count += 1
        if self.image_5:
            count += 1
        return count
    
    def clean(self):
        if self.old_price and self.old_price <= self.price:
            raise ValidationError({'old_price': 'Старая цена должна быть больше текущей'})
        
        if self.stones and not self.stone_type:
            raise ValidationError({'stone_type': 'Укажите тип камней'})
        
        if self.stones and self.stone_type == 'none':
            raise ValidationError({'stone_type': 'Выберите конкретный тип камня'})
        
        if self.stone_weight and not self.stones:
            raise ValidationError({'stones': 'Отметьте наличие камней для указания веса'})
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        """Возвращает URL для просмотра товара""" #Создать URL по имени маршрута
        return reverse('store:product_detail', kwargs={ #имя маршрута, параметры которые подставятся в юрл, id товара и slug товара
            'product_id': self.id,
            'slug': self.slug
        })

    def delete(self, *args, **kwargs):
        """Удаляем файлы изображений при удалении товара"""
        if self.image and os.path.isfile(self.image.path):
            os.remove(self.image.path)
        if self.image_2 and os.path.isfile(self.image_2.path):
            os.remove(self.image_2.path)
        if self.image_3 and os.path.isfile(self.image_3.path):
            os.remove(self.image_3.path)
        if self.image_4 and os.path.isfile(self.image_4.path):
            os.remove(self.image_4.path)
        if self.image_5 and os.path.isfile(self.image_5.path):
            os.remove(self.image_5.path)
        super().delete(*args, **kwargs)


# Сигнал для автоматического создания корзины при создании пользователя
@receiver(post_save, sender=User)
def create_user_cart(sender, instance, created, **kwargs):
    """
    Автоматически создает корзину для нового пользователя
    """
    if created:
        Cart.objects.create(user=instance)


class Cart(models.Model):
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        blank=True, 
        null=True, 
        related_name='carts',
        verbose_name='Пользователь'
    )
    session_key = models.CharField(max_length=40, blank=True, verbose_name='Ключ сессии')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    
    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'
        ordering = ['-updated_at']
    
    def __str__(self):
        if self.user:
            return f"Корзина {self.user.email}"
        return f"Корзина (гость) {self.session_key}"
    
    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())
    
    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart, 
        on_delete=models.CASCADE, 
        related_name='items',
        verbose_name='Корзина'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='cart_items',
        verbose_name='Товар'
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name='Количество')
    added_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')
    
    class Meta:
        verbose_name = 'Элемент корзины'
        verbose_name_plural = 'Элементы корзины'
        unique_together = ['cart', 'product']
    
    def __str__(self):
        return f"{self.cart} - {self.product.name} x{self.quantity}"
    
    @property
    def total_price(self):
        """Общая сумма позиции корзины"""
        if self.product and self.product.price is not None and self.quantity is not None:
            return self.product.price * self.quantity
        return Decimal('0')
    
    def clean(self):
        if self.quantity > self.product.available_quantity:
            raise ValidationError({
                'quantity': f'Доступно только {self.product.available_quantity} единиц'
            })


class Order(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('confirmed', 'Подтверждён'),
        ('processing', 'В обработке'),
        ('shipped', 'Отправлен'),
        ('delivered', 'Доставлен'),
        ('cancelled', 'Отменён'),
    ]
    
    DELIVERY_CHOICES = [
        ('courier', 'Курьером'),
        ('pickup', 'Самовывоз'),
        ('mail', 'Почтой'),
    ]
    
    PAYMENT_CHOICES = [
        ('card_online', 'Картой онлайн'),
        ('sbp', 'СБП'),
        ('cash', 'Наличными'),
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='orders',
        verbose_name='Пользователь'
    )
    order_number = models.CharField(
        max_length=20, 
        unique=True, 
        editable=False, 
        default=generate_order_number,
        verbose_name='Номер заказа'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name='Статус')
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Общая сумма')
    delivery_address = models.TextField(verbose_name='Адрес доставки')
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_CHOICES, verbose_name='Способ доставки')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, verbose_name='Способ оплаты')
    gift_wrap = models.BooleanField(default=False, verbose_name='Подарочная упаковка')
    gift_message = models.TextField(blank=True, verbose_name='Поздравительная открытка')
    comment = models.TextField(blank=True, verbose_name='Комментарий')
    delivered_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата доставки')
    
    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Заказ #{self.order_number} - {self.get_status_display()}"
    
    def calculate_total(self):
        """Расчет общей суммы заказа"""
        total = Decimal('0')
        for item in self.items.all():
            total += item.price * item.quantity
        self.total_price = total
        self.save(update_fields=['total_price'])
        return total


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE, 
        related_name='items',
        verbose_name='Заказ'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='order_items',
        verbose_name='Товар'
    )
    product_name = models.CharField(max_length=200, verbose_name='Название товара')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')
    quantity = models.PositiveIntegerField(verbose_name='Количество')
    
    class Meta:
        verbose_name = 'Элемент заказа'
        verbose_name_plural = 'Элементы заказа'
    
    def __str__(self):
        return f"{self.order.order_number} - {self.product_name} x{self.quantity}"
    
    @property
    def total_price(self):
        """Общая сумма позиции заказа"""
        if self.price is not None and self.quantity is not None:
            return self.price * self.quantity
        return Decimal('0')
    
    def save(self, *args, **kwargs):
        # Автоматически заполняем поля, если они пустые
        if self.product:
            if not self.product_name:
                self.product_name = self.product.name
            if not self.price:
                self.price = self.product.price
        
        super().save(*args, **kwargs)
        self.order.calculate_total()


class Review(models.Model):
    RATING_CHOICES = [(i, i) for i in range(1, 6)]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='reviews',
        verbose_name='Автор'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='reviews',
        verbose_name='Товар'
    )
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, verbose_name='Оценка')
    comment = models.TextField(verbose_name='Текст отзыва')
    image = models.ImageField(upload_to='reviews/', blank=True, null=True, verbose_name='Изображение')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    moderated = models.BooleanField(default=False, verbose_name='Промодерирован')
    
    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ['-created_at']
        unique_together = ['user', 'product']
    
    def __str__(self):
        return f"{self.user.email} - {self.product.name} ({self.rating}★)"


class Wishlist(models.Model):
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='wishlist',
        verbose_name='Пользователь'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='in_wishlists',
        verbose_name='Товар'
    )
    added_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')
    
    class Meta:
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранное'
        unique_together = ['user', 'product']
        ordering = ['-added_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.product.name}"