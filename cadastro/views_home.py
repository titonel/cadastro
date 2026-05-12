import io
from datetime import date

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect

from .models import (
    Prestador, Especialidade, ContratoUpload,
    UploadProducao, TipoRelatorioProducao, StatusImportacao,
)
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
    """Módulo de acompanhamento de produção — upload de XLS do SIRESP."""
    if request.method == "POST":
        arquivo = request.FILES.get("arquivo_producao")
        tipo = request.POST.get("tipo", TipoRelatorioProducao.CONSULTA)

        if not arquivo:
            messages.error(request, "Nenhum arquivo selecionado.")
            return redirect("cadastro:acompanhamento")

        ext = arquivo.name.rsplit(".", 1)[-1].lower()
        if ext not in ("xls", "xlsx"):
            messages.error(request, "Formato inválido. Envie um arquivo .xls ou .xlsx.")
            return redirect("cadastro:acompanhamento")

        upload = UploadProducao(
            arquivo=arquivo,
            tipo=tipo,
            status=StatusImportacao.PENDENTE,
        )
        upload.save()

        # Processa imediatamente com o parser adequado ao tipo de relatório
        try:
            if tipo == TipoRelatorioProducao.CIRURGIA_EXAME:
                from .producao_siresp_exames import processar_upload_exames as _processar
            else:
                from .producao_siresp import processar_upload as _processar
            _processar(upload.pk)
            messages.success(
                request,
                f"Arquivo importado com sucesso: "
                f"{upload.total_agendas} agenda(s) e "
                f"{upload.total_medicos} registro(s) de médico(s) processados. "
                f"Período: {upload.periodo_display}.",
            )
        except Exception as exc:
            upload.status = StatusImportacao.ERRO
            upload.erro_processamento = str(exc)
            upload.save()
            messages.error(request, f"Erro ao processar o arquivo: {exc}")

        return redirect("cadastro:acompanhamento")

    # GET — lista os uploads existentes
    uploads_consulta = UploadProducao.objects.filter(
        tipo=TipoRelatorioProducao.CONSULTA
    ).order_by("-enviado_em")[:20]

    uploads_cirurgia = UploadProducao.objects.filter(
        tipo=TipoRelatorioProducao.CIRURGIA_EXAME
    ).order_by("-enviado_em")[:20]

    context = {
        "uploads_consulta": uploads_consulta,
        "uploads_cirurgia": uploads_cirurgia,
        "tipo_choices": TipoRelatorioProducao.choices,
    }
    return render(request, "cadastro/acompanhamento.html", context)


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

    servicos = []
    for s in prestador.servicos.all().order_by("tipo_servico", "descricao"):
        servicos.append({
            "descricao": s.descricao or s.get_tipo_servico_display(),
            "cod": s.pk,
            "agenda": "",
            "estimativa": s.quantidade_estimada_mes,
            "valor_unit": float(s.valor_unitario),
            "producao": {},
        })

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
