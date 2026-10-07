from django.urls import path
from . import api
from .commands import COMMANDS
urlpatterns=[path('commands/'+name+'/',api.command_view(name)) for name in COMMANDS]+[
 path('lookups/<str:resource>/',api.Lookups.as_view()),
 path('register/<int:pk>/',api.Register.as_view()),
 path('mine/corrections/',api.MyCorrections.as_view()),
 path('mine/',api.Mine.as_view()),path('report/',api.Report.as_view()),
 path('export/',api.Export.as_view()),path('reconcile/',api.Reconcile.as_view()),
 path('lesson-progress/<int:pk>/',api.LessonProgress.as_view()),
 path('history/<int:pk>/',api.History.as_view()),
 path('<str:resource>/',api.Records.as_view()),
]
