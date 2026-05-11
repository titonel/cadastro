import io
from datetime import date

from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404

from .models import Prestador, Especialidade, ContratoUpload
from .relatorio_producao import criar_relatorio


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


def indicadores(request):
    """Módulo de indicadores / dashboards — em construção."""
    return render(request, "cadastro/indicadores.html", {})


# ─────────────────────────────────────────────────────────────────────────────
# Módulo Relatório
# ─────────────────────────────────────────────────────────────────────────────

def relatorio(request):
    """Seleção de prestador e período para gerar o relatório de produção."""
    prestadores = Prestador.objects.filter(ativo=True).order_by("nome_empresa")
    hoje = date.today()
    context = {
        "prestadores": prestadores,
        "mes_atual": hoje.month,
        "ano_atual": hoje.year,
        "anos": range(2024, hoje.year + 2),
        "meses": [
            (1, "Janeiro"), (2, "Fevereiro"), (3, "Março"), (4, "Abril"),
            (5, "Maio"), (6, "Junho"), (7, "Julho"), (8, "Agosto"),
            (9, "Setembro"), (10, "Outubro"), (11, "Novembro"), (12, "Dezembro"),
        ],
    }
    return render(request, "cadastro/relatorio.html", context)


def relatorio_download(request, pk):
    """Gera e devolve o relatório XLSX de um prestador para um período."""
    prestador = get_object_or_404(Prestador, pk=pk)
    mes_ini = int(request.GET.get("mes", date.today().month))
    ano_ini = int(request.GET.get("ano", date.today().year))

    # Monta lista de serviços a partir dos ServicoContratado vinculados
    servicos = []
    for s in prestador.servicos.all().order_by("tipo_servico", "descricao"):
        servicos.append({
            "descricao": s.descricao or s.get_tipo_servico_display(),
            "cod": s.pk,
            "agenda": "",
            "estimativa": s.quantidade_estimada_mes,
            "valor_unit": float(s.valor_unitario),
            "producao": {},  # sem dados lançados: relatório em branco para preenchimento
        })

    # Fallback: se não há serviços cadastrados, cria um genérico
    if not servicos:
        especialidade_nome = (
            prestador.especialidades.first().nome
            if prestador.especialidades.exists()
            else "Serviço"
        )
        servicos = [{
            "descricao": especialidade_nome,
            "cod": 1,
            "agenda": "",
            "estimativa": 0,
            "valor_unit": 0.0,
            "producao": {},
        }]

    especialidade_nome = (
        prestador.especialidades.first().nome
        if prestador.especialidades.exists()
        else ""
    )

    wb = criar_relatorio(
        mes_ini=mes_ini,
        ano_ini=ano_ini,
        nome_empresa=prestador.nome_empresa,
        especialidade=especialidade_nome,
        servicos=servicos,
        prestador_nome=prestador.nome_representante or prestador.nome_empresa,
        crm=prestador.crm_representante or "",
    )

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    mes_fim = 1 if mes_ini == 12 else mes_ini + 1
    ano_fim = ano_ini + 1 if mes_ini == 12 else ano_ini
    filename = (
        f"relatorio_{prestador.nome_empresa.replace(' ', '_')}_"
        f"{mes_ini:02d}{ano_ini}_{mes_fim:02d}{ano_fim}.xlsx"
    )

    response = HttpResponse(
        buf,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
