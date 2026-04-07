from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os

# Регистрируем русский шрифт
try:
    # Для macOS/Linux
    font_path = '/System/Library/Fonts/Supplemental/Arial.ttf'
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('Arial', font_path))
        RUSSIAN_FONT = 'Arial'
    else:
        # Альтернативный путь для Linux
        font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
            RUSSIAN_FONT = 'DejaVuSans'
        else:
            RUSSIAN_FONT = 'Helvetica'
except:
    RUSSIAN_FONT = 'Helvetica'

def export_products_to_pdf(modeladmin, request, queryset):
    """Экспорт выбранных товаров в PDF с таблицей на русском языке"""
    
    # Создаём ответ с PDF типом
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="products_report.pdf"'
    
    # Создаём PDF документ
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    # Стили с русским шрифтом
    styles = getSampleStyleSheet()
    
    # Стиль для заголовка
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName=RUSSIAN_FONT,
        fontSize=16,
        alignment=1,  # Центр
        spaceAfter=20,
        textColor=colors.HexColor('#2c3e50')
    )
    
    # Стиль для обычного текста
    normal_style = ParagraphStyle(
        'NormalRussian',
        parent=styles['Normal'],
        fontName=RUSSIAN_FONT,
        fontSize=10
    )
    
    # Элементы документа
    elements = []
    
    # Заголовок
    elements.append(Paragraph("Отчёт по товарам", title_style))
    elements.append(Spacer(1, 20))
    
    # Данные для таблицы (русские заголовки)
    data = [
        ['ID', 'Название', 'Цена', 'Тип серебра', 'В наличии']
    ]
    
    for product in queryset:
        data.append([
            str(product.id),
            product.name,
            f"{product.price} ₽",
            product.get_silver_type_display(),
            str(product.available_quantity)
        ])
    
    # Создаём таблицу
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3a4a5a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#e8dcc8')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), RUSSIAN_FONT),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f0e8')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d4c5b0')),
        ('FONTNAME', (0, 1), (-1, -1), RUSSIAN_FONT),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(table)
    
    # Добавляем дату генерации
    elements.append(Spacer(1, 30))
    from django.utils import timezone
    date_paragraph = Paragraph(
        f"Дата генерации: {timezone.now().strftime('%d.%m.%Y %H:%M')}",
        normal_style
    )
    elements.append(date_paragraph)
    
    # Строим PDF
    doc.build(elements)
    
    # Получаем PDF из буфера
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response

export_products_to_pdf.short_description = "📄 Экспорт товаров в PDF (русский)"