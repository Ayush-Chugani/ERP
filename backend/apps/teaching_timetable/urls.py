from django.urls import path
from .api import CommandView, RecordsView, OccurrencesView, ExportView, BulkView, ImportView, COMMANDS, command_view
from .lookups import LookupView
from .reports import HistoryView, WorkloadView, WorkloadExportView, PreviewView, AvailabilityView

urlpatterns = [path('commands/' + operation + '/', command_view(operation)) for operation in COMMANDS] + [
    path('revisions/<int:pk>/history/', HistoryView.as_view()),
    path('workload/', WorkloadView.as_view()),
    path('workload/export/', WorkloadExportView.as_view()),
    path('availability/', AvailabilityView.as_view()),
    path('conflicts/', PreviewView.as_view()),
    path('bulk-assignments/', BulkView.as_view()),
    path('import-allocations/', ImportView.as_view()),
    path('lookups/<slug:resource>/', LookupView.as_view()),
    path('commands/<slug:operation>/', CommandView.as_view()),
    path('occurrences/', OccurrencesView.as_view()),
    path('export/', ExportView.as_view()),
    path('<slug:resource>/', RecordsView.as_view()),
]
