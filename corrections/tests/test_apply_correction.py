# corrections/tests/test_apply_correction.py

from django.test import TestCase
from corrections.models import Correction, Item
from corrections.views import apply_correction


class ApplyCorrectionTestCase(TestCase):
    def setUp(self):
        self.subject_item = Item.objects.create(value="Math", score=0.8)

        self.hyp1 = Item.objects.create(value="Mathematics", score=0.9, approved=False)
        self.hyp2 = Item.objects.create(value="Applied Math", score=0.95, approved=False)
        self.hyp_approved = Item.objects.create(value="Pure Math", score=0.7, approved=True)

        self.correction_pending = Correction.objects.create(
            subject=self.subject_item,
            scope_id=0,
            status=Correction.STATUS_PENDING
        )
        self.correction_pending.hypotheses.set([self.hyp1])

        self.correction_approved = Correction.objects.create(
            subject=self.subject_item,
            scope_id=1,
            status=Correction.STATUS_APPROVED
        )
        self.correction_approved.hypotheses.set([self.hyp_approved])

        self.correction_invalid = Correction.objects.create(
            subject=self.subject_item,
            scope_id=2,
            status=Correction.STATUS_INVALID
        )
        self.hyp_reviewer = Item.objects.create(
            value="Reviewer Fix", score=1.0, approved=True, suggested_by_reviewer=True
        )
        self.correction_invalid.hypotheses.set([self.hyp_reviewer])

    def test_no_correction_no_hypotheses_returns_subject(self):
        subject = Item(value="Physics", score=0.5)
        result = apply_correction(subject, [], scope_id=999)
        self.assertEqual(result, subject)

    def test_no_correction_with_hypotheses_returns_best(self):
        hyp_a = Item(value="A", score=0.6)
        hyp_b = Item(value="B", score=0.9)
        result = apply_correction(self.subject_item, [hyp_a, hyp_b], scope_id=999)
        self.assertEqual(result.value, "B")

    def test_approved_no_approved_hyp_and_no_new_hypotheses(self):
        self.hyp_approved.approved = False
        self.hyp_approved.save()
        result = apply_correction(self.subject_item, [], scope_id=1)
        fresh_corr = Correction.objects.get(pk=self.correction_approved.pk)
        best_in_corr = fresh_corr.hypotheses.order_by('-score').first()
        self.assertEqual(result.value, best_in_corr.value)

    def test_approved_with_better_new_hypothesis(self):
        new_hyp = Item.objects.create(value="Super Math", score=0.99)
        result = apply_correction(self.subject_item, [new_hyp], scope_id=1)
        fresh_corr = Correction.objects.get(pk=self.correction_approved.pk)
        self.assertEqual(fresh_corr.status, Correction.STATUS_PENDING)
        self.assertEqual(result.value, "Pure Math")
        
    def test_approved_with_worse_new_hypotheses(self):
        new_hyp = Item.objects.create(value="Bad Math", score=0.5)
        result = apply_correction(self.subject_item, [new_hyp], scope_id=1)
        fresh_corr = Correction.objects.get(pk=self.correction_approved.pk)
        self.assertEqual(fresh_corr.status, Correction.STATUS_APPROVED)
        self.assertEqual(result.value, "Pure Math")

    def test_approved_no_approved_hyp_but_new_better_hypothesis(self):
        self.hyp_approved.approved = False
        self.hyp_approved.save()
        new_hyp = Item.objects.create(value="Best Math", score=0.92)
        result = apply_correction(self.subject_item, [new_hyp], scope_id=1)
        fresh_corr = Correction.objects.get(pk=self.correction_approved.pk)
        self.assertEqual(fresh_corr.status, Correction.STATUS_PENDING)
        best_in_corr = fresh_corr.hypotheses.order_by('-score').first()
        self.assertEqual(result.value, best_in_corr.value)

    def test_pending_with_empty_hypotheses_returns_best_from_correction(self):
        result = apply_correction(self.subject_item, [], scope_id=0)
        fresh_corr = Correction.objects.get(pk=self.correction_pending.pk)
        best_in_corr = fresh_corr.hypotheses.order_by('-score').first()
        self.assertEqual(result.value, best_in_corr.value)

    def test_invalid_resets_reviewer_hypotheses_and_returns_best_new(self):
        new_hyp = Item.objects.create(value="Fixed Math", score=0.88)
        result = apply_correction(self.subject_item, [new_hyp], scope_id=2)
        self.assertEqual(result.value, "Fixed Math")

    def test_invalid_no_new_hypotheses_returns_subject(self):
        result = apply_correction(self.subject_item, [], scope_id=2)
        self.assertEqual(result, self.subject_item)

    def test_multiple_hypotheses_same_max_score(self):
        h1 = Item(value="Same1", score=0.99)
        h2 = Item(value="Same2", score=0.99)
        result = apply_correction(self.subject_item, [h1, h2], scope_id=999)
        self.assertIn(result.value, ["Same1", "Same2"])

    def test_unsaved_items_in_hypotheses_handled_correctly(self):
        unsaved_hyp = Item(value="Unsaved", score=0.99)
        result = apply_correction(self.subject_item, [unsaved_hyp], scope_id=999)
        self.assertEqual(result.value, "Unsaved")

    def test_idempotency_approved_stays_approved_if_no_better_hyp(self):
        apply_correction(self.subject_item, [], scope_id=1)
        fresh_corr = Correction.objects.get(pk=self.correction_approved.pk)
        self.assertEqual(fresh_corr.status, Correction.STATUS_APPROVED)

    def test_idempotency_pending_stays_pending_and_returns_existing_best(self):

        worse_hyp = Item.objects.create(value="Worse", score=0.5)
        result = apply_correction(self.subject_item, [worse_hyp], scope_id=0)
        self.assertEqual(result.value, "Mathematics")
