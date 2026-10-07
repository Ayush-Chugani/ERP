from django.urls import path
from . import views
from .serializers import COMMANDS
urlpatterns=[path('commands/'+op+'/',views.command_view(op)) for op in COMMANDS]+[path('cycles/<int:pk>/targets/',views.ResultTargets.as_view()),path('available/',views.Available.as_view()),path('cycles/<int:pk>/questionnaire/',views.Questionnaire.as_view()),path('cycles/<int:pk>/submit/',views.Submit.as_view()),path('cycles/<int:pk>/results/',views.Results.as_view()),path('cycles/<int:pk>/export/',views.Export.as_view()),path('cycles/<int:pk>/text/',views.TextReview.as_view()),path('public/cycles/<int:pk>/results/',views.PublicResults.as_view()),path('questionnaires/<int:pk>/readiness/',views.Readiness.as_view()),path('<str:resource>/',views.Records.as_view())]
