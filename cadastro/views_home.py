from django.shortcuts import render
from .models import Prestador, Especialidade, ContratoUpload


def home(request):
    """Landing page principal com os 4 módulos do sistema."""
    context = {
        "total_prestadores": Prestador.objects.filter(ativo=True).count(),
        "total_especialidades": Especialidade.objects.filter(ativa=True).count(),
        "total_contratos": ContratoUpload.objects.count(),
    }
    return render(request, "cadastro/home.html", context)


def acompanhamento(request):
    """Módulo de acompanhamento de produção — em construção."""
    return render(request, "cadastro/acompanhamento.html", {})


def relatorio(request):
    """Módulo de relatórios — em construção."""
    return render(request, "cadastro/relatorio.html", {})


def indicadores(request):
    """Módulo de indicadores / dashboards — em construção."""
    return render(request, "cadastro/indicadores.html", {})
