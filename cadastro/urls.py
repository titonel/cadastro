from django.urls import path
from . import views

app_name = "cadastro"

urlpatterns = [
    # Prestadores
    path("", views.prestador_list, name="prestador_list"),
    path("novo/", views.prestador_create, name="prestador_create"),
    path("<int:pk>/", views.prestador_detail, name="prestador_detail"),
    path("<int:pk>/editar/", views.prestador_edit, name="prestador_edit"),
    path("<int:pk>/excluir/", views.prestador_delete, name="prestador_delete"),
    # Importação de contratos
    path("importar/", views.contrato_upload, name="contrato_upload"),
    path("importar/<int:pk>/revisao/", views.contrato_revisao, name="contrato_revisao"),
    path("importar/<int:pk>/ignorar/", views.contrato_ignorar, name="contrato_ignorar"),
]
