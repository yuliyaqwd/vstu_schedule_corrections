from django.contrib import admin
from django.utils.html import format_html
from .models import ContextElement, Item, Correction

class ContextElementAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'important', 'created_count']
    list_filter = ['important', 'key']
    search_fields = ['key', 'value']
    list_per_page = 20
    
    def created_count(self, obj):
        count = obj.item_set.count()
        return f"{count} items"
    created_count.short_description = 'Используется в'

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['value_short', 'score', 'approved', 'suggested_by_reviewer', 'context_count', 'created_at']
    list_filter = ['approved', 'suggested_by_reviewer', 'created_at']
    search_fields = ['value']
    readonly_fields = ['created_at']
    
    def value_short(self, obj):
        return obj.value[:50] + '...' if len(obj.value) > 50 else obj.value
    value_short.short_description = 'Значение'
    
    def context_count(self, obj):
        return obj.context.count()
    context_count.short_description = 'Контекст'

class HypothesisInline(admin.TabularInline):
    model = Correction.hypotheses.through
    extra = 1
    verbose_name = "Гипотеза"
    verbose_name_plural = "Гипотезы"

@admin.register(Correction)
class CorrectionAdmin(admin.ModelAdmin):
    list_display = ['id', 'subject_short', 'status_display', 'scope_id', 'hypotheses_count', 'created_at']
    list_filter = ['status', 'scope_id', 'created_at']
    search_fields = ['subject__value', 'hypotheses__value']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [HypothesisInline]
    
    def subject_short(self, obj):
        return obj.subject.value[:30] + '...' if len(obj.subject.value) > 30 else obj.subject.value
    subject_short.short_description = 'Объект'
    
    def status_display(self, obj):
        status_config = {
            Correction.STATUS_PENDING: ('Ожидает проверки', '#ffe6e6'),
            Correction.STATUS_APPROVED: ('Подтверждена', '#e6ffe6'),
            Correction.STATUS_INVALID: ('Аннулирована', '#f0f0f0')
        }
        text, color = status_config.get(obj.status, ('Неизвестно', '#ffffff'))
        return format_html(
            '<span style="background: {}; padding: 4px 8px; border-radius: 3px; display: inline-block; min-width: 120px; text-align: center;">{}</span>',
            color, text
        )
    status_display.short_description = 'Статус'
    
    def hypotheses_count(self, obj):
        return obj.hypotheses.count()
    hypotheses_count.short_description = 'Гипотез'

# Регистрируем модели
admin.site.register(ContextElement, ContextElementAdmin)

# Настройки админки
admin.site.site_header = "Система корректировки расписаний"
admin.site.site_title = "Система корректировки расписаний"
admin.site.index_title = "Панель управления"
