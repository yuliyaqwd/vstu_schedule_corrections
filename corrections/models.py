# corrections/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Set, Tuple, Optional
import math

class ContextElement(models.Model):
    """Элемент контекста для Item"""
    key = models.CharField(max_length=100, verbose_name="Ключ")
    value = models.CharField(max_length=255, verbose_name="Значение")
    important = models.BooleanField(default=False, verbose_name="Важный элемент")

    class Meta:
        verbose_name = "Элемент контекста"
        verbose_name_plural = "Элементы контекста"
        unique_together = ['key', 'value']

    def __str__(self):
        return f"{self.key}: {self.value} {'⭐' if self.important else ''}"


class ItemManager(models.Manager):
    def create_with_reviewer_flag(self, **kwargs):
        """Создает Item с установленным флагом suggested_by_reviewer"""
        kwargs['suggested_by_reviewer'] = True
        return self.create(**kwargs)
    
    def get_or_create_with_score(self, value: str, score: Decimal = None, **kwargs):
        """Создает или получает Item с корректным score"""
        if score is not None:
            # Нормализуем score
            score = self.normalize_score(score)
        
        # Пытаемся найти существующий Item
        item = self.filter(value=value).first()
        if item:
            if score is not None and item.score != score:
                item.score = score
                item.save()
            return item, False
        
        # Создаем новый
        defaults = {
            'score': score or Decimal('0.5'),
            'suggested_by_reviewer': True,
            **kwargs
        }
        return self.create(value=value, **defaults), True
    
    @staticmethod
    def normalize_score(score) -> Decimal:
        """Нормализует score: округляет до 0.1 и проверяет диапазон"""
        if isinstance(score, (int, float)):
            score = Decimal(str(score))
        elif isinstance(score, str):
            score = Decimal(score)
        
        # Округляем до 1 знака после запятой
        score = score.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
        
        # Проверяем диапазон 0.0-1.0
        if score < Decimal('0.0'):
            score = Decimal('0.0')
        elif score > Decimal('1.0'):
            score = Decimal('1.0')
        
        return score


class Item(models.Model):
    """Корректируемый объект или гипотеза замены"""
    value = models.TextField(verbose_name="Значение")
    context = models.ManyToManyField(ContextElement, blank=True, verbose_name="Контекст")
    
    # Score строго от 0.0 до 1.0 с шагом 0.1
    score = models.DecimalField(
        max_digits=3,  # X.X формат, например 0.5, 1.0
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="Оценка качества",
        default=Decimal('0.5')
    )
    
    approved = models.BooleanField(default=False, verbose_name="Подтверждена")
    suggested_by_reviewer = models.BooleanField(default=True, verbose_name="Создана ревьювером")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Создан")
    
    objects = ItemManager()

    class Meta:
        verbose_name = "Объект/Гипотеза"
        verbose_name_plural = "Объекты/Гипотезы"
        ordering = ['-score']
        constraints = [
            models.CheckConstraint(
                check=models.Q(score__gte=Decimal('0.0')) & models.Q(score__lte=Decimal('1.0')),
                name='score_range_check'
            )
        ]

    def __str__(self):
        score_str = f" (score: {self.score})" if self.score is not None else ""
        return f"'{self.value[:50]}{'...' if len(self.value) > 50 else ''}'{score_str}"

    def clean(self):
        """Валидация score - строго 0.0-1.0 с шагом 0.1"""
        if self.score is not None:
            try:
                # Преобразуем в Decimal для точных вычислений
                if isinstance(self.score, (int, float, str)):
                    score_decimal = Decimal(str(self.score))
                else:
                    score_decimal = self.score
                
                # Проверяем, что это число с максимум 1 знаком после запятой
                if score_decimal.as_tuple().exponent < -1:
                    raise ValidationError({
                        'score': 'Score должен иметь максимум 1 знак после запятой (например: 0.1, 0.5, 1.0)'
                    })
                
                # Проверяем, что кратно 0.1
                if (score_decimal * 10) % 1 != 0:
                    raise ValidationError({
                        'score': 'Score должен быть кратен 0.1 (допустимые значения: 0.0, 0.1, 0.2, ..., 1.0)'
                    })
                
                # Проверяем диапазон
                if score_decimal < Decimal('0.0') or score_decimal > Decimal('1.0'):
                    raise ValidationError({
                        'score': 'Score должен быть в диапазоне от 0.0 до 1.0 включительно'
                    })
                
                # Нормализуем score
                self.score = Item.objects.normalize_score(score_decimal)
                
            except (ValueError, TypeError) as e:
                raise ValidationError({
                    'score': f'Некорректное значение score: {e}'
                })
    
    def save(self, *args, **kwargs):
        # Всегда устанавливаем suggested_by_reviewer=True
        self.suggested_by_reviewer = True
        
        # Нормализуем score перед сохранением
        if self.score is not None:
            self.score = Item.objects.normalize_score(self.score)
        
        # Полная валидация
        self.full_clean()
        super().save(*args, **kwargs)

    def get_important_context(self) -> List[ContextElement]:
        """Получить важные элементы контекста"""
        return list(self.context.filter(important=True))

    def get_all_context(self) -> List[ContextElement]:
        """Получить все элементы контекста"""
        return list(self.context.all())

    def get_context_as_dict(self) -> dict:
        """Получить контекст в виде словаря"""
        return {ctx.key: ctx.value for ctx in self.context.all()}

    def context_display(self) -> str:
        """Отображение контекста для админки"""
        important = self.get_important_context()
        if important:
            return ", ".join([f"{ctx.key}:{ctx.value}" for ctx in important])
        return "Нет важного контекста"

    def matches_context(self, other_context: Set[Tuple[str, str]], 
                       check_important_only: bool = False) -> float:
        """
        Проверяет соответствие контекстов.
        Возвращает коэффициент совпадения от 0.0 до 1.0.
        """
        if not self.context.exists():
            return 0.0
        
        my_context = set()
        for ctx in self.context.all():
            if not check_important_only or ctx.important:
                my_context.add((ctx.key, ctx.value))
        
        if not my_context:
            return 0.0
        
        # Вычисляем коэффициент совпадения
        intersection = len(my_context.intersection(other_context))
        return intersection / len(my_context)


class CorrectionManager(models.Manager):
    def find_by_subject_and_context(self, subject_value: str, 
                                   context_items: List[ContextElement] = None,
                                   scope_id: int = 0) -> models.QuerySet:
        """Найти корректировки по значению subject и контексту"""
        base_qs = self.filter(
            subject__value=subject_value,
            scope_id=scope_id
        ).select_related('subject').prefetch_related('hypotheses', 'subject__context')
        
        if not context_items:
            return base_qs
        
        # Преобразуем контекст в set для сравнения
        context_set = {(ctx.key, ctx.value) for ctx in context_items}
        
        # Сортируем по совпадению контекста
        corrections = []
        for correction in base_qs:
            match_score = correction.subject.matches_context(context_set, check_important_only=True)
            corrections.append((match_score, correction))
        
        # Сортируем по убыванию совпадения
        corrections.sort(key=lambda x: x[0], reverse=True)
        return [corr for _, corr in corrections]


class Correction(models.Model):
    """Корректировка с набором гипотез"""
    STATUS_PENDING = 0
    STATUS_APPROVED = 1
    STATUS_INVALID = 2
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'PENDING - Ожидает проверки'),
        (STATUS_APPROVED, 'APPROVED - Подтверждена'),
        (STATUS_INVALID, 'INVALID - Аннулирована'),
    ]

    subject = models.ForeignKey(
        Item, 
        on_delete=models.CASCADE,
        related_name='correction_subject',
        verbose_name="Корректируемый объект"
    )
    
    hypotheses = models.ManyToManyField(
        Item, 
        related_name='correction_hypotheses',
        verbose_name="Гипотезы"
    )
    
    status = models.IntegerField(choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="Статус")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Создана")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлена")
    scope_id = models.IntegerField(default=0, verbose_name="Область видимости")
    
    objects = CorrectionManager()

    class Meta:
        verbose_name = "Корректировка"
        verbose_name_plural = "Корректировки"
        indexes = [
            models.Index(fields=['scope_id', 'status']),
            models.Index(fields=['subject']),
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]
        ordering = ['-updated_at']

    def __str__(self):
        return f"Корректировка #{self.id} - {self.get_status_display()}"

    def clean(self):
        """Валидация: НЕ проверяем ManyToMany при создании объекта"""
        # Проверка ManyToMany полей делается в методе save()
        # после того, как объект будет сохранен
        pass

    def save(self, *args, **kwargs):
        # Сохраняем объект
        super().save(*args, **kwargs)
        
        # После сохранения проверяем уникальность score
        self._ensure_unique_scores()

    def _ensure_unique_scores(self):
        """Гарантирует уникальность score в гипотезах корректировки"""
        try:
            hypotheses = list(self.hypotheses.all().order_by('-score'))
            scores_seen = set()
            items_seen = set()
            to_remove = []
            
            for hyp in hypotheses:
                # Проверяем, что гипотеза не дублируется
                if hyp.id in items_seen:
                    to_remove.append(hyp)
                    continue
                else:
                    items_seen.add(hyp.id)
                
                if hyp.score is None:
                    continue
                    
                # Нормализуем score для сравнения
                normalized_score = Item.objects.normalize_score(hyp.score)
                if normalized_score in scores_seen:
                    to_remove.append(hyp)
                else:
                    scores_seen.add(normalized_score)
            
            # Удаляем гипотезы с дублирующимися score или сами дубли
            for hyp in to_remove:
                try:
                    self.hypotheses.remove(hyp)
                except:
                    pass  # Игнорируем ошибку если гипотеза уже удалена
        except:
            pass  # Игнорируем ошибки в этом методе

    def add_hypothesis(self, hypothesis: Item, check_uniqueness: bool = True):
        """Добавить гипотезу с проверкой уникальности score"""
        if not self.pk:
            raise ValidationError("Корректировка должна быть сохранена перед добавлением гипотез")
            
        # Проверяем, что гипотеза еще не добавлена
        if self.hypotheses.filter(id=hypothesis.id).exists():
            return  # Уже добавлена, ничего не делаем
            
        if check_uniqueness:
            # Получаем нормализованные scores существующих гипотез
            existing_scores = {
                Item.objects.normalize_score(h.score) 
                for h in self.hypotheses.all() 
                if h.score is not None
            }
            
            if hypothesis.score is not None:
                normalized_new_score = Item.objects.normalize_score(hypothesis.score)
                if normalized_new_score in existing_scores:
                    raise ValidationError(
                        f'Гипотеза с score={normalized_new_score} уже существует в этой корректировке'
                    )
        
        # Устанавливаем флаг suggested_by_reviewer
        hypothesis.suggested_by_reviewer = True
        hypothesis.save()
        
        # Используем add() с bulk=False для избежания дублирования
        self.hypotheses.add(hypothesis)

    def get_optimal_hypothesis(self) -> Item:
        """Получить оптимальную гипотезу"""
        if self.status == self.STATUS_APPROVED:
            approved_hypothesis = self.hypotheses.filter(approved=True).first()
            if approved_hypothesis:
                return approved_hypothesis
        
        # Для статуса INVALID возвращаем subject
        if self.status == self.STATUS_INVALID:
            return self.subject
        
        # Ищем гипотезу с максимальным score
        best_hypothesis = self.hypotheses.exclude(score__isnull=True).order_by('-score').first()
        return best_hypothesis if best_hypothesis else self.subject

    def get_status_display_with_color(self) -> str:
        """Получить отображение статуса с HTML цветом"""
        status_map = {
            self.STATUS_PENDING: ('PENDING', 'warning'),
            self.STATUS_APPROVED: ('APPROVED', 'success'),
            self.STATUS_INVALID: ('INVALID', 'danger'),
        }
        name, color = status_map.get(self.status, ('UNKNOWN', 'secondary'))
        return f'<span class="badge badge-{color}">{name}</span>'

    def get_hypotheses_by_score(self) -> List[Item]:
        """Получить гипотезы, сгруппированные по уникальным score"""
        # Используем distinct() по score
        return list(self.hypotheses.all().order_by('-score'))

    def get_context_match_score(self, context_items: List[ContextElement]) -> float:
        """Получить оценку совпадения контекста"""
        if not context_items:
            return 0.0
        
        context_set = {(ctx.key, ctx.value) for ctx in context_items}
        return self.subject.matches_context(context_set, check_important_only=True)
    
    def get_hypothesis_by_score(self, score: Decimal) -> Optional[Item]:
        """Получить гипотезу по конкретному score"""
        if score is None:
            return None
        
        normalized_score = Item.objects.normalize_score(score)
        return self.hypotheses.filter(score=normalized_score).first()
