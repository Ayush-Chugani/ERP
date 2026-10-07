from django.urls import path
from . import views
from .serializers import COMMANDS
urlpatterns=[path('commands/'+name+'/',views.command_view(name)) for name in COMMANDS]+[path('bulk/',views.Batch.as_view()),path('reports/<str:resource>/',views.Report.as_view()),path('mine/',views.Mine.as_view()),path('events/<int:pk>/marks/',views.Roster.as_view()),path('export/<str:resource>/',views.Export.as_view()),path('<str:resource>/',views.Records.as_view())]
