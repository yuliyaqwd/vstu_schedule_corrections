# corrections/test_apply_correction.py

from django.test import TestCase
from .models import Correction, Item
from .views import apply_correction


class ApplyCorrectionTestCase(TestCase):
    def setUp(self):
        # Создаём предмет и "гипотезы" (они тоже Item!)
        self.subject_item = Item.objects.create(value="Math", score=0.8)

        # Гипотезы = Item с дополнительными флагами
        self.hyp1 = Item.objects.create(value="Mathematics", score=0.9, approved=False)
        self.hyp2 = Item.objects.create(value="Applied Math", score=0.95, approved=False)
        self.hyp_approved = Item.objects.create(value="Pure Math", score=0.7, approved=True)

        # Корректировка: PENDING
        self.correction_pending = Correction.objects.create(
            subject=self.subject_item,
            scope_id=0,
            status=Correction.STATUS_PENDING
        )
        self.correction_pending.hypotheses.set([self.hyp1])

        # Корректировка: APPROVED
        self.correction_approved = Correction.objects.create(
            subject=self.subject_item,
            scope_id=1,
            status=Correction.STATUS_APPROVED
        )
        self.correction_approved.hypotheses.set([self.hyp_approved])

        # Корректировка: INVALID с гипотезой от рецензента
        self.correction_invalid = Correction.objects.create(
            subject=self.subject_item,
            scope_id=2,
            status=Correction.STATUS_INVALID
        )
        self.hyp_reviewer = Item.objects.create(
            value="Reviewer Fix", score=1.0, approved=True, suggested_by_reviewer=True
        )
        self.correction_invalid.hypotheses.set([self.hyp_reviewer])

    def test_apply_correction_no_existing_correction(self):
        """Нет корректировки → возвращается лучшая из входных гипотез (Item)"""
        new_hyp = Item(value="Advanced Math", score=0.99)  # не сохраняем в БД!
        hypotheses = [new_hyp]
        subject = Item(value="Physics", score=0.5)

        result = apply_correction(subject, hypotheses, scope_id=999)
        self.assertEqual(result.value, "Advanced Math")

    def test_apply_correction_approved_with_better_hypothesis(self):
        """APPROVED: приходит лучшая гипотеза → добавляется, статус → PENDING"""
        new_hyp = Item.objects.create(value="Super Math", score=0.99)
        hypotheses = [new_hyp]

        result = apply_correction(self.subject_item, hypotheses, scope_id=1)

        self.correction_approved.refresh_from_db()
        self.assertEqual(self.correction_approved.status, Correction.STATUS_PENDING)
        self.assertIn(new_hyp, self.correction_approved.hypotheses.all())
        self.assertEqual(result.value, "Pure Math")  # утверждённая остаётся

    def test_apply_correction_approved_no_approved_hypothesis(self):
        """APPROVED, но нет approved=True → возвращается лучшая из всех"""
        self.hyp_approved.approved = False
        self.hyp_approved.save()

        new_hyp = Item.objects.create(value="Best Math", score=0.92)
        hypotheses = [new_hyp]

        result = apply_correction(self.subject_item, hypotheses, scope_id=1)

        best_in_correction = max(
            self.correction_approved.hypotheses.all(), key=lambda h: h.score
        )
        self.assertEqual(result.value, best_in_correction.value)

    def test_apply_correction_pending_adds_hypotheses(self):
        """PENDING: все входные гипотезы добавляются"""
        new_hyp = Item.objects.create(value="Pending Math", score=0.96)
        hypotheses = [new_hyp]

        result = apply_correction(self.subject_item, hypotheses, scope_id=0)

        self.correction_pending.refresh_from_db()
        self.assertIn(new_hyp, self.correction_pending.hypotheses.all())
        self.assertEqual(result.value, "Pending Math")

    def test_apply_correction_invalid_resets_reviewer_hypotheses(self):
        """INVALID: сбрасывает гипотезы от рецензента"""
        new_hyp = Item.objects.create(value="Fixed Math", score=0.88)
        hypotheses = [new_hyp]

        result = apply_correction(self.subject_item, hypotheses, scope_id=2)

        self.correction_invalid.refresh_from_db()
        self.assertEqual(self.correction_invalid.status, Correction.STATUS_PENDING)

        self.hyp_reviewer.refresh_from_db()
        self.assertEqual(self.hyp_reviewer.score, 0)
        self.assertFalse(self.hyp_reviewer.approved)

        self.assertIn(new_hyp, self.correction_invalid.hypotheses.all())
        self.assertEqual(result.value, "Fixed Math")
