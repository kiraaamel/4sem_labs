from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """
    Кастомный менеджер для модели User с email в качестве логина.
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email обязателен')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Суперпользователь должен иметь is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Суперпользователь должен иметь is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

def generate_order_number():
    """
    Генерирует уникальный номер заказа.
    Формат: ORD-YYYYMMDD-XXXX (где XXXX - случайные символы)
    """
    date_part = timezone.now().strftime('%Y%m%d')
    random_part = str(uuid.uuid4())[:4].upper()
    return f"ORD-{date_part}-{random_part}"


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True, verbose_name='Email')
    phone = models.CharField(max_length=20, blank=True, verbose_name='Телефон')
    bonus_points = models.IntegerField(default=0, verbose_name='Бонусные баллы')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()  # ← кастомный менеджер

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.email

    def is_product_in_wishlist(self, product_id):
        return self.wishlist.filter(product_id=product_id).exists()


class Category(models.Model):
    """
    Категория товара с поддержкой вложенности.
    """
    name = models.CharField(
        max_length=255,
        verbose_name='Название'
    )
    slug = models.SlugField(
        unique=True,
        verbose_name='URL-идентификатор'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Ювелирное изделие.
    """
    # Основная информация
    name = models.CharField(
        max_length=255,
        verbose_name='Название'
    )
    slug = models.SlugField(
        unique=True,
        verbose_name='URL-идентификатор'
    )
    description = models.TextField(
        verbose_name='Описание'
    )
    
    # Цены и наличие
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Цена'
    )
    old_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='Старая цена'
    )
    country = models.CharField(
    max_length=100,
    blank=True,
    default='Италия',
    verbose_name='Страна производства'
)
    stock_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name='Количество на складе'
    )
    reserved_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name='Зарезервированное количество'
    )
    
    # Связь с категорией
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='products',
        verbose_name='Категория'
    )
    
    # Характеристики ювелирного изделия
    metal = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Металл'
    )
    fineness = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name='Проба'
    )
    weight = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='Вес (г)'
    )
    size = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Размер'
    )
    stones = models.BooleanField(
        default=False,
        verbose_name='Наличие камней'
    )
    stone_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Тип камня'
    )
    collection = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Коллекция'
    )
    
    # Изображение (одно фото, упрощённо)
    image = models.ImageField(
        upload_to='products/',
        blank=True,
        null=True,
        verbose_name='Изображение'
    )
    
    # Мета-информация
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products_created',
        verbose_name='Создал'
    )

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['category', 'price']),
        ]

    def __str__(self):
        return self.name

    @property
    def available_quantity(self):
        """
        Доступное количество товара (на складе минус зарезервированное).
        """
        return self.stock_quantity - self.reserved_quantity

    @property
    def average_rating(self):
        """
        Средний рейтинг товара на основе отзывов.
        """
        reviews = self.reviews.filter(moderated=True)
        if not reviews:
            return 0
        total = sum(review.rating for review in reviews)
        return round(total / reviews.count(), 1)

    @property
    def reviews_count(self):
        """
        Количество отзывов на товар.
        """
        return self.reviews.filter(moderated=True).count()

    def is_in_wishlist(self, user):
        """
        Проверяет, находится ли товар в избранном у указанного пользователя.
        """
        if not user or not user.is_authenticated:
            return False
        return Wishlist.objects.filter(user=user, product=self).exists()

    @property
    def discount_percent(self):
        """
        Процент скидки (если есть старая цена).
        """
        if self.old_price and self.old_price > self.price:
            return int((1 - self.price / self.old_price) * 100)
        return 0


class Cart(models.Model):
    """
    Корзина покупок (привязана к пользователю или сессии).
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart',
        verbose_name='Пользователь'
    )
    session_key = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Ключ сессии'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'

    def __str__(self):
        if self.user:
            return f"Корзина {self.user.email}"
        return f"Корзина гостя (сессия: {self.session_key})"

    @property
    def total_price(self):
        """
        Общая стоимость всех товаров в корзине.
        """
        return sum(item.total_price for item in self.items.all())

    @property
    def total_items(self):
        """
        Общее количество товаров в корзине.
        """
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    """
    Элемент корзины (связь товара и корзины с количеством).
    """
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Корзина'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name='Товар'
    )
    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name='Количество'
    )
    added_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата добавления'
    )

    class Meta:
        verbose_name = 'Элемент корзины'
        verbose_name_plural = 'Элементы корзины'
        unique_together = ('cart', 'product')

    def clean(self):
        """
        Проверка наличия товара на складе перед сохранением.
        """
        if self.quantity > self.product.available_quantity:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                f'Доступно только {self.product.available_quantity} единиц товара "{self.product.name}"'
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"

    @property
    def total_price(self):
        """
        Стоимость этой позиции (цена товара * количество).
        """
        if self.product and self.product.price is not None and self.quantity is not None:
            return self.product.price * self.quantity
        return 0


class Order(models.Model):
    """
    Заказ покупателя.
    """
    class Status(models.TextChoices):
        NEW = 'new', 'Новый'
        CONFIRMED = 'confirmed', 'Подтверждён'
        SHIPPED = 'shipped', 'Отправлен'
        DELIVERED = 'delivered', 'Доставлен'
        CANCELLED = 'cancelled', 'Отменён'

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name='Пользователь'
    )
    order_number = models.CharField(
        max_length=50,
        unique=True,
        default=generate_order_number,
        verbose_name='Номер заказа'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        verbose_name='Статус'
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,  # ← значение по умолчанию
        verbose_name='Общая стоимость'
    )
    delivery_address = models.TextField(
        verbose_name='Адрес доставки'
    )
    delivery_method = models.CharField(
        max_length=100,
        verbose_name='Способ доставки'
    )
    payment_method = models.CharField(
        max_length=100,
        verbose_name='Способ оплаты'
    )
    gift_wrap = models.BooleanField(
        default=False,
        verbose_name='Подарочная упаковка'
    )
    gift_message = models.TextField(
        blank=True,
        verbose_name='Текст открытки'
    )
    comment = models.TextField(
        blank=True,
        verbose_name='Комментарий к заказу'
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата получения'
    )
    def save(self, *args, **kwargs):
        """
        Автоматически вычисляем общую стоимость заказа.
        """
        if not self.total_price and self.pk:
            # Если заказ уже существует, считаем сумму по позициям
            self.total_price = sum(item.total_price for item in self.items.all())
        super().save(*args, **kwargs)
    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f"Заказ №{self.order_number}"


class OrderItem(models.Model):
    """
    Позиция заказа (товар в заказе).
    """
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
        verbose_name='Товар'
    )
    product_name = models.CharField(
        max_length=255,
        verbose_name='Название товара (на момент заказа)'
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Цена на момент заказа'
    )
    quantity = models.PositiveIntegerField(
        verbose_name='Количество'
    )

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"

    @property
    def total_price(self):
        """
        Стоимость этой позиции (цена * количество).
        """
        if self.price is not None and self.quantity is not None:
            return self.price * self.quantity
        return 0


class Review(models.Model):
    """
    Отзыв на товар от покупателя.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name='Пользователь'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name='Товар'
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Оценка'
    )
    comment = models.TextField(
        blank=True,
        verbose_name='Текст отзыва'
    )
    image = models.ImageField(
        upload_to='reviews/',
        blank=True,
        null=True,
        verbose_name='Фото'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата'
    )
    moderated = models.BooleanField(
        default=False,
        verbose_name='Промодерировано'
    )
    def clean(self):
        """
        Проверка, что пользователь действительно покупал этот товар.
        """
        has_purchased = Order.objects.filter(
            user=self.user,
            items__product=self.product,
            status=Order.Status.DELIVERED
        ).exists()
        
        if not has_purchased:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                'Вы можете оставить отзыв только на товары, которые вы купили и получили.'
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        unique_together = ('user', 'product')
        ordering = ['-created_at']

    def __str__(self):
        return f"Отзыв {self.user.email} на {self.product.name} - {self.rating}★"


class Wishlist(models.Model):
    """
    Список избранного пользователя.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='wishlist',
        verbose_name='Пользователь'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='wishlisted_by',
        verbose_name='Товар'
    )
    added_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата добавления'
    )

    class Meta:
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранное'
        unique_together = ('user', 'product')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.email} -> {self.product.name}"