from django.utils import timezone
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Product, Category, User, Order, Cart, Review

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(label='Email', required=True)
    first_name = forms.CharField(label='Имя', max_length=150, required=True)
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
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'old_price', 
                  'stock_quantity', 'category', 'silver_type', 'fineness',
                  'weight', 'size', 'stones', 'stone_type', 'stone_weight',
                  'collection', 'image', 'image_2', 'image_3', 'image_4', 'image_5', 'instruction_file', 'external_link']
        # Пункт 4: widgets
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Опишите изделие...'}), #высота поля 5 строк
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название товара'}), #как выглядит форма: добавления css класса и подсказки placeholder
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'url-идентификатор'}),
            'instruction_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'external_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'ссылка для вашего удобства'}),
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
        product.updated_at = timezone.now()
        if commit:
            product.save() #сохраняем сам объект
            self.save_m2m() # Сохраняем many-to-many связи (если будут)
        return product


class ReviewForm(forms.ModelForm):
    """Форма для отзыва о товаре"""
    
    class Meta:
        model = Review
        fields = ['rating', 'comment', 'image']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Поделитесь впечатлениями о товаре...'}),
            'rating': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def clean_comment(self):
        comment = self.cleaned_data.get('comment')
        if comment and len(comment) < 10:
            raise forms.ValidationError('Отзыв должен содержать минимум 10 символов')
        return comment

class CategoryForm(forms.ModelForm):
    """Форма для создания/редактирования категории"""
    
    class Meta:
        model = Category
        fields = ['name', 'slug', 'description', 'parent', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Описание категории...'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название категории'}),
        }
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if Category.objects.filter(name=name).exists():
            raise forms.ValidationError('Категория с таким названием уже существует')
        return name