from django import template
from store.models import Product

register = template.Library()

# 16. Простой тег
@register.simple_tag
def current_time():
    "возвращает текущее время"
    from django.utils import timezone
    return timezone.now().strftime("%H:%M:%S")

# 17. Тег с контекстом Имеет доступ к переменным шаблона через context
@register.simple_tag(takes_context=True)
def cart_count(context):
    "возвращает кол-во товаров в корзине"
    request = context.get('request')
    if request and hasattr(request, 'cart'):
        return request.cart.total_items
    return 0

# 18. Тег, возвращающий QuerySet Запрашивает данные из базы и возвращает их
@register.simple_tag
def popular_products(limit=4):
    "возвращает популярные товары"
    return Product.available.all().order_by('-created_at')[:limit]