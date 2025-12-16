# corrections/admin_auth.py
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.contrib.admin.sites import AdminSite
from django.http import HttpResponseRedirect
from django.urls import reverse

class PublicAdminSite(AdminSite):
    
    def login(self, request, extra_context=None):
        # Автоматически логинимся как первый суперпользователь
        users = User.objects.filter(is_superuser=True)
        if users.exists():
            from django.contrib.auth import login
            login(request, users.first())
            return HttpResponseRedirect(reverse('admin:index'))
        return super().login(request, extra_context)
    
    def has_permission(self, request):
        # Всегда разрешаем доступ
        return True

# Создаем публичную админку
public_admin = PublicAdminSite(name='public_admin')

# Регистрируем модели в публичной админке (используем тот же код что в admin.py)
from .models import ContextElement, Item, Correction
from .admin import ContextElementAdmin, ItemAdmin, CorrectionAdmin

public_admin.register(ContextElement, ContextElementAdmin)
public_admin.register(Item, ItemAdmin)
public_admin.register(Correction, CorrectionAdmin)
