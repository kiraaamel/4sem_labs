# store/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Product, Category, Review, Order, Collection

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(label='Email', required=True)
    first_name = forms.CharField(label='Имя', max_length=150, required=True) #поле для ввода многострочного текста
    last_name = forms.CharField(label='Фамилия', max_length=150, required=True)
    phone = forms.CharField(label='Телефон', required=False)
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone = self.cleaned_data['phone']
        if commit:
            user.save()
        return user

class UserLoginForm(AuthenticationForm):
    username = forms.EmailField(label='Email')

class ProductForm(forms.ModelForm):
    """Форма для создания/редактирования товара"""
    collections = forms.ModelMultipleChoiceField(
        queryset=Collection.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'collections-checkbox'}),
        label='Коллекции'
    )
    class Meta:
        model = Product
        #какие поля включаем
        fields = ['name', 'description', 'price', 'old_price', 
                  'stock_quantity', 'category', 'silver_type', 'fineness',
                  'weight', 'size', 'stones', 'stone_type', 'stone_weight',
                   'image', 'image_2', 'image_3', 'image_4', 'image_5',
                  'instruction_file', 'external_link', 'collections']
        # Пункт 4: widgets как выглядят поля
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Опишите изделие...'}), #высота поля 5 строк
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название товара'}), #как выглядит форма: добавления css класса и подсказки placeholder
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'url-идентификатор'}),
            'instruction_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'external_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
        }
        #labels - русские названия полей
        labels = {
            'name': 'Название товара',
            'slug': 'URL-идентификатор',
            'description': 'Описание',
            'price': 'Цена (₽)',
            'old_price': 'Старая цена (₽)',
            'stock_quantity': 'Количество на складе',
            'category': 'Категория',
            'silver_type': 'Тип серебра',
            'fineness': 'Проба',
            'weight': 'Вес (г)',
            'size': 'Размер',
            'stones': 'Наличие драгоценных камней',
            'stone_type': 'Тип камня',
            'stone_weight': 'Вес камней (карат)',
            'collection': 'Коллекция',
            'image': 'Главное фото',
            'image_2': 'Дополнительное фото 2',
            'image_3': 'Дополнительное фото 3',
            'image_4': 'Дополнительное фото 4',
            'image_5': 'Дополнительное фото 5',
            'instruction_file': 'Инструкция к товару',
            'external_link': 'Внешняя ссылка',
        }
        
        #help_texts - подсказки под полями
        help_texts = {
            'name': 'Введите полное название изделия',
            'slug': 'Останется пустым — заполнится автоматически',
            'price': 'Цена в рублях',
            'stock_quantity': 'Сколько единиц товара на складе',
            'instruction_file': 'Загрузите PDF инструкцию (опционально)',
            'external_link': 'Ссылка на видеообзор или сайт производителя',
        }
        
        #error_messages - свои сообщения об ошибках
        error_messages = {
            'name': {
                'required': 'Пожалуйста, введите название товара',
                'max_length': 'Название слишком длинное (максимум 200 символов)',
            },
            'price': {
                'required': 'Укажите цену товара',
            },
            'slug': {
                'unique': 'Товар с таким URL уже существует',
            },
        }
    
    # Пункт 5: clean_<fieldname> — валидация конкретного поля
    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price and price <= 0:
            raise forms.ValidationError('Цена должна быть больше 0')
        return price
    
    def clean_stock_quantity(self):
        quantity = self.cleaned_data.get('stock_quantity')
        if quantity and quantity < 0:
            raise forms.ValidationError('Количество не может быть отрицательным')
        return quantity
    
    # Пункт 6: save с commit=True
    def save(self, commit=True):
            product = super().save(commit=False) #создаем объект но не сохраняем в БД
            # Дополнительная логика перед сохранением
            if commit:
                product.save()#сохраняем сам объект
                # Сохраняем выбранные коллекции (ManyToMany)
                self.save_m2m()
                # Сохраняем связи с коллекциями
                if hasattr(self, 'cleaned_data'):
                    self.instance.collections.set(self.cleaned_data['collections'])
            return product
        

class ReviewForm(forms.ModelForm):
    """Форма для отзыва о товаре"""
    
    class Meta:
        model = Review
        fields = ['rating', 'comment', 'image']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Поделитесь впечатлениями о товаре...'}), 
            'rating': forms.Select(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
    
    def clean_comment(self):
        comment = self.cleaned_data.get('comment')
        if comment and len(comment) < 10:
            raise forms.ValidationError('Отзыв должен содержать минимум 10 символов')
        return comment