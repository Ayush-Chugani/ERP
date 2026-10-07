from django.urls import path
from . import api
from .commands import COMMANDS
urlpatterns=[
    path('commands/'+name+'/',api.command_view(name),name='registration-'+name) for name in COMMANDS
]+[
    path('import/parse/',api.ImportParse.as_view()),
    path('bulk/',api.Bulk.as_view()),
    path('mine/offerings/',api.PersonalOfferings.as_view()),
    path('mine/',api.Personal.as_view()),
    path('lookups/<str:resource>/',api.Lookups.as_view()),
    path('export/<str:resource>/',api.Export.as_view()),
    path('reconciliation/',api.Reconciliation.as_view()),
    path('<str:resource>/',api.Records.as_view()),
    path('<str:resource>/<int:pk>/',api.Detail.as_view()),
]
