from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('corrections/', views.CorrectionListView.as_view(), name='correction_list'),
    #path('api/apply-correction/', views.ApplyCorrectionAPI.as_view(), name='apply_correction'),
    path('upload/', views.upload_schedule, name='upload_schedule'),
    path('export/corrections/', views.export_corrections, name='export_corrections'),
    path('export/schedule/', views.export_schedule_with_corrections, name='export_schedule'),
]
