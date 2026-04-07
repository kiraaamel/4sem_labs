from django import template

register = template.Library()
#форматирование цены
@register.filter
def rub_format(value):
    try:
        return f"{float(value):,.0f}".replace(',', ' ') + " ₽" #запятая разделитель тысяч, .0ф - без копеек
    except:
        return value
#звезды рейтинга
@register.filter
def stars(rating):
    if not rating:
        return ''
    full = int(rating)
    empty = 5 - full
    return '★' * full + '☆' * empty