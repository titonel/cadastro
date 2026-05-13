from django.urls import path
from . import views
from . import views_home

app_name = "cadastro"

urlpatterns = [
    # ── Landing page ──────────────────────────────────────────────────────────
    path("", views_home.home, name="home"),

    # ── Módulo: Acompanhamento de Produção ────────────────────────────────────
    path("acompanhamento/", views_home.acompanhamento, name="acompanhamento"),

    # ── Módulo: Relatório ─────────────────────────────────────────────────────
    path("relatorio/", views_home.relatorio, name="relatorio"),
    path("relatorio/<int:pk>/download/", views_home.relatorio_download, name="relatorio_download"),

    # ── Módulo: Indicadores ───────────────────────────────────────────────────
    path("indicadores/", views_home.indicadores, name="indicadores"),
    path("indicadores/prestador/", views_home.indicadores_prestador, name="indicadores_prestador"),

    # ── Módulo: Cadastro — Prestadores ────────────────────────────────────────
    path("prestadores/", views.prestador_list, name="prestador_list"),
    path("prestadores/novo/", views.prestador_create, name="prestador_create"),
    path("prestadores/<int:pk>/", views.prestador_detail, name="prestador_detail"),
    path("prestadores/<int:pk>/editar/", views.prestador_edit, name="prestador_edit"),
    path("prestadores/<int:pk>/excluir/", views.prestador_delete, name="prestador_delete"),

    # ── Diagnóstico temporário ────────────────────────────────────────────────
    path("diagnostico/producao/", views_home.diagnostico_producao, name="diagnostico_producao"),

    # ── Módulo: Cadastro — Médicos ────────────────────────────────────────────
    path("medicos/", views.medico_list, name="medico_list"),
    path("medicos/novo/", views.medico_create, name="medico_create"),
    path("medicos/<int:pk>/", views.medico_detail, name="medico_detail"),
    path("medicos/<int:pk>/editar/", views.medico_edit, name="medico_edit"),
    path("medicos/<int:pk>/excluir/", views.medico_delete, name="medico_delete"),

    # ── Módulo: Mapeamento de Agendas ─────────────────────────────────────────
    path("prestadores/<int:prestador_pk>/mapeamentos/", views.mapeamento_list, name="mapeamento_list"),
    path("agendas/autocomplete/", views.agendas_autocomplete, name="agendas_autocomplete"),

    # ── Módulo: Cadastro — Importação de Contratos via PDF ────────────────────
    path("contrato/upload/", views.contrato_upload, name="contrato_upload"),
    path("contrato/<int:pk>/revisar/", views.contrato_revisao, name="contrato_revisao"),
    path("contrato/<int:pk>/ignorar/", views.contrato_ignorar, name="contrato_ignorar"),
]
