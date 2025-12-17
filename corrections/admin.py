from django import forms
from django.contrib import admin
from django.urls import path, reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.utils.html import format_html
from django.contrib.admin.views.decorators import staff_member_required
from .models import ContextElement, Item, Correction


# =============== AJAX View для создания контекста ===============
@staff_member_required
@require_POST
@csrf_protect
def add_contextelement_ajax(request):
    key = request.POST.get('key', '').strip()
    value = request.POST.get('value', '').strip()
    important = request.POST.get('important') == 'on'

    if not key or not value:
        return JsonResponse({'error': 'Ключ и значение обязательны.'}, status=400)

    obj, created = ContextElement.objects.get_or_create(
        key=key,
        value=value,
        defaults={'important': important}
    )
    if not created and obj.important != important:
        obj.important = important
        obj.save()

    return JsonResponse({
        'id': obj.id,
        'repr': f"{obj.key}: {obj.value}" + (" ⭐" if obj.important else ""),
    })


# =============== Форма для Item ===============
class ItemAdminForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['value', 'score', 'approved', 'suggested_by_reviewer', 'context']
        widgets = {
            'context': admin.widgets.FilteredSelectMultiple("Элементы контекста", is_stacked=False),
        }

    class Media:
        js = ('admin/js/jquery.init.js',)


# =============== Админка: Item ===============
@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    form = ItemAdminForm
    list_display = ['value_short', 'score_badge', 'approved_icon', 'context_preview', 'created_at']
    list_filter = ['approved', 'suggested_by_reviewer', 'created_at']
    search_fields = ['value', 'context__key', 'context__value']
    readonly_fields = ['created_at', 'add_context_section']  # ← current_context_list удалён

    fieldsets = (
        ('Основное значение', {
            'fields': ('value', 'score', 'approved', 'suggested_by_reviewer')
        }),
        ('➕ Добавить элемент контекста', {
            'fields': ('add_context_section',),
        }),
        ('Выбор существующих элементов', {
            'fields': ('context',),
            'description': '<small>Выберите дополнительные уже существующие элементы.</small>',
        }),
        ('Служебное', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def add_context_section(self, obj):
        ajax_url = reverse('admin:corrections_item_add_context_ajax')
        return format_html(
            '''
            <div style="margin-top: 8px;">
                <input type="text" id="id_new_context_key" placeholder="Ключ" style="width: 120px; margin-right: 8px;">
                <input type="text" id="id_new_context_value" placeholder="Значение" style="width: 160px; margin-right: 8px;">
                <label style="display: inline-flex; align-items: center; gap: 4px; cursor: pointer;">
                    <input type="checkbox" id="id_new_context_important"> ⭐ Важный
                </label>
                <button type="button" id="add-context-btn" class="button"
                        style="margin-left: 12px; padding: 4px 10px; font-size: 0.9em;">
                    ➕ Добавить
                </button>
                <div id="context-msg" style="margin-top: 6px; min-height: 20px; font-size: 0.9em;"></div>
            </div>
            <script>
            (function($) {{
                $('#add-context-btn').on('click', function() {{
                    const key = $('#id_new_context_key').val().trim();
                    const value = $('#id_new_context_value').val().trim();
                    const important = $('#id_new_context_important').is(':checked');
                    const btn = $(this);
                    const msg = $('#context-msg');

                    if (!key || !value) {{
                        msg.html('<span style="color: #d00;">Заполните ключ и значение.</span>');
                        return;
                    }}

                    btn.prop('disabled', true).text('Добавление...');

                    $.ajax({{
                        url: '{ajax_url}',
                        type: 'POST',
                         {{
                            key: key,
                            value: value,
                            important: important ? 'on' : '',
                            csrfmiddlewaretoken: $('input[name=csrfmiddlewaretoken]').val()
                        }},
                        success: function(data) {{
                            if (typeof SelectBox !== 'undefined') {{
                                SelectBox.add('id_context', data.repr, data.id);
                            }}
                            const $select = $('#id_context');
                            if (!$select.find('option[value="' + data.id + '"]').length) {{
                                const option = new Option(data.repr, data.id, true, true);
                                $select.append(option);
                            }}
                            $('#id_new_context_key, #id_new_context_value').val('');
                            $('#id_new_context_important').prop('checked', false);
                            msg.html('<span style="color: #28a745;">✓ Элемент добавлен и будет сохранён!</span>');
                        }},
                        error: function(xhr) {{
                            const err = xhr.responseJSON?.error || 'Ошибка сервера';
                            msg.html('<span style="color: #d00;">' + err + '</span>');
                        }},
                        complete: function() {{
                            btn.prop('disabled', false).text('➕ Добавить');
                        }}
                    }});
                }});
            }})(django.jQuery);
            </script>
            ''',
            ajax_url=ajax_url
        )
    add_context_section.short_description = ""

    # --- Вспомогательные методы отображения ---
    def value_short(self, obj):
        return (obj.value[:60] + '…') if len(obj.value) > 60 else obj.value or "—"
    value_short.short_description = 'Значение'

    def score_badge(self, obj):
        if obj.score is None:
            return "—"
        color = '#28a745' if obj.score >= 0.8 else '#ffc107' if obj.score >= 0.5 else '#dc3545'
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 8px; font-weight: bold;">{}</span>',
            color, obj.score
        )
    score_badge.short_description = 'Оценка'

    def approved_icon(self, obj):
        return format_html('<span style="font-size: 1.1em;">{}</span>', '✅' if obj.approved else '—')
    approved_icon.short_description = 'Подтверждён'

    def context_preview(self, obj):
        contexts = obj.context.all()
        if not contexts:
            return "—"
        preview = ", ".join(f"{c.key}:{c.value}" for c in contexts[:2])
        return preview + ("…" if contexts.count() > 2 else "")
    context_preview.short_description = 'Контекст'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'add-context-ajax/',
                self.admin_site.admin_view(add_contextelement_ajax),
                name='corrections_item_add_context_ajax'
            ),
        ]
        return custom_urls + urls

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if 'empty_label' not in kwargs:
            kwargs['empty_label'] = ''
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# =============== ContextElement ===============
@admin.register(ContextElement)
class ContextElementAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'important', 'used_in_items_count']
    list_editable = ['important']
    list_filter = ['important', 'key']
    search_fields = ['key', 'value']
    ordering = ['key', 'value']

    def used_in_items_count(self, obj):
        return obj.item_set.count() or "—"
    used_in_items_count.short_description = 'Используется в'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        kwargs['empty_label'] = ''
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# =============== Correction ===============
class HypothesisInline(admin.TabularInline):
    model = Correction.hypotheses.through
    extra = 1
    verbose_name = "Гипотеза"
    verbose_name_plural = "Гипотезы"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        kwargs['empty_label'] = ''
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Correction)
class CorrectionAdmin(admin.ModelAdmin):
    list_display = ['id', 'subject_short', 'status_badge', 'scope_id', 'hypotheses_count', 'created_at']
    list_filter = ['status', 'scope_id', 'created_at']
    search_fields = ['subject__value', 'hypotheses__value']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [HypothesisInline]
    exclude = ('hypotheses',)

    def subject_short(self, obj):
        if not obj.subject:
            return "—"
        v = obj.subject.value
        return (v[:50] + '…') if len(v) > 50 else v
    subject_short.short_description = 'Объект'

    def status_badge(self, obj):
        config = {
            Correction.STATUS_PENDING: ('Ожидает', '#ffcc00', '🕒'),
            Correction.STATUS_APPROVED: ('Готово', '#28a745', '✅'),
            Correction.STATUS_INVALID: ('Отменено', '#dc3545', '❌'),
        }
        text, bg, icon = config.get(obj.status, ('—', '#6c757d', '❓'))
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 10px; font-size: 0.85em; display: inline-flex; '
            'align-items: center; gap: 4px; min-width: 85px; justify-content: center;">'
            '{} {}</span>',
            bg, icon, text
        )
    status_badge.short_description = 'Статус'

    def hypotheses_count(self, obj):
        return obj.hypotheses.count() or "—"
    hypotheses_count.short_description = 'Гипотез'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        kwargs['empty_label'] = ''
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# =============== Заголовки ===============
admin.site.site_header = "✨ Система корректировки расписаний"
admin.site.site_title = "ВолгГТУ — Админка"
admin.site.index_title = "Управление данными"
