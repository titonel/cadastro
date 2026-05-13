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
            upload.refresh_from_db()
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
    """Hub do módulo de indicadores com links para os sub-dashboards."""
    return render(request, "cadastro/indicadores.html", {})


def indicadores_prestador(request):
    """
    Dashboard de metas por prestador.

    Lógica de vínculo corrigida — duas camadas:

    1. Meta mensal (linha tracejada):
       ServicoContratado.quantidade_estimada_mes do prestador selecionado,
       agrupado por ServicoContratado.descricao (nome da agenda).

    2. Produção real (linha sólida):
       ProducaoMedico.agend_totais, somada por agenda e por mês,
       filtrada pelos médicos cadastrados que pertencem ao prestador.

       Cadeia: ProducaoMedico.nome_medico (MAIÚSCULAS no SIRESP)
               ↔  Medico.nome_completo.upper()
               →  Medico.prestador == prestador_selecionado

       Fallback (sem médicos cadastrados para o prestador):
       Usa ProducaoAgenda.agend_totais cruzando pelo nome da agenda,
       igual à lógica original.  Exibe aviso no template.

    Filtros GET:
      prestador      — pk do Prestador
      especialidade  — pk da Especialidade
      mes_ini        — "AAAA-MM"
      mes_fim        — "AAAA-MM"
    """
    import json
    import calendar
    from datetime import date
    from collections import defaultdict

    from .models import (
        Prestador, Especialidade, Medico,
        ServicoContratado, UploadProducao,
        ProducaoAgenda, ProducaoMedico,
    )

    prestadores    = Prestador.objects.filter(ativo=True).order_by("nome_empresa")
    especialidades = Especialidade.objects.filter(ativa=True).order_by("nome")

    prestador_pk     = request.GET.get("prestador", "")
    especialidade_pk = request.GET.get("especialidade", "")
    mes_ini_str      = request.GET.get("mes_ini", "")
    mes_fim_str      = request.GET.get("mes_fim", "")

    # ── Opções de mês a partir dos uploads confirmados ───────────────────────
    uploads_qs = UploadProducao.objects.filter(
        status="confirmado",
        data_inicio_periodo__isnull=False,
    ).order_by("data_inicio_periodo")

    periodos_disponiveis = []
    seen = set()
    for u in uploads_qs:
        chave = u.data_inicio_periodo.strftime("%Y-%m")
        if chave not in seen:
            seen.add(chave)
            periodos_disponiveis.append((
                chave,
                u.data_inicio_periodo.strftime("%b/%Y").capitalize(),
            ))

    if not periodos_disponiveis:
        hoje = date.today()
        for i in range(11, -1, -1):
            m, y = hoje.month - i, hoje.year
            while m <= 0:
                m += 12; y -= 1
            chave = f"{y}-{m:02d}"
            from calendar import month_abbr
            periodos_disponiveis.append((chave, f"{month_abbr[m]}/{y}".capitalize()))

    meses_opcoes    = periodos_disponiveis
    mes_ini_default = periodos_disponiveis[0][0]  if periodos_disponiveis else date.today().strftime("%Y-%m")
    mes_fim_default = periodos_disponiveis[-1][0] if periodos_disponiveis else date.today().strftime("%Y-%m")
    mes_ini_sel     = mes_ini_str or mes_ini_default
    mes_fim_sel     = mes_fim_str or mes_fim_default

    ctx_base = {
        "prestadores": prestadores,
        "especialidades": especialidades,
        "meses_opcoes": meses_opcoes,
        "mes_ini_selecionado": mes_ini_sel,
        "mes_fim_selecionado": mes_fim_sel,
        "especialidade_selecionada": especialidade_pk,
    }

    if not prestador_pk:
        return render(request, "cadastro/indicadores_prestador.html", {
            **ctx_base,
            "prestador_selecionado": "",
            "prestador_obj": None,
            "series": [], "series_json": "[]", "labels_json": "[]",
            "periodo_label": "", "aviso_sem_medicos": False,
        })

    prestador_obj = get_object_or_404(Prestador, pk=prestador_pk, ativo=True)

    # ── Serviços contratados ─────────────────────────────────────────────────
    servicos_qs = ServicoContratado.objects.filter(
        prestador=prestador_obj
    ).select_related("especialidade")
    if especialidade_pk:
        servicos_qs = servicos_qs.filter(especialidade__pk=especialidade_pk)
    servicos = list(servicos_qs)

    # ── Intervalo de períodos ────────────────────────────────────────────────
    periodos_no_range = [
        (chave, label)
        for chave, label in periodos_disponiveis
        if mes_ini_sel <= chave <= mes_fim_sel
    ] or periodos_disponiveis

    labels = [label for _, label in periodos_no_range]
    chaves = [chave for chave, _ in periodos_no_range]

    def chave_to_ini(chave):
        y, m = int(chave[:4]), int(chave[5:])
        return date(y, m, 1)

    ini_global = chave_to_ini(chaves[0])
    fim_global = date(
        int(chaves[-1][:4]),
        int(chaves[-1][5:]),
        calendar.monthrange(int(chaves[-1][:4]), int(chaves[-1][5:]))[1],
    )

    uploads_no_range = UploadProducao.objects.filter(
        status="confirmado",
        data_inicio_periodo__gte=ini_global,
        data_inicio_periodo__lte=fim_global,
    )

    # ── Médicos do prestador (nomes em UPPER para cruzamento) ────────────────
    medicos_do_prestador = set(
        Medico.objects.filter(prestador=prestador_obj, ativo=True)
        .values_list("nome_completo", flat=True)
    )
    nomes_upper = {n.strip().upper() for n in medicos_do_prestador}

    aviso_sem_medicos = len(nomes_upper) == 0

    # ── Construir índice de produção ─────────────────────────────────────────
    # Estrutura: { nome_agenda_upper: { chave_mes: total_agend } }
    prod_index = defaultdict(lambda: defaultdict(int))

    if nomes_upper:
        # Caminho principal: soma ProducaoMedico dos médicos do prestador
        medicos_qs = (
            ProducaoMedico.objects
            .filter(agenda__upload__in=uploads_no_range)
            .select_related("agenda__upload")
        )
        for pm in medicos_qs:
            if pm.nome_medico.strip().upper() in nomes_upper:
                chave_mes  = pm.agenda.upload.data_inicio_periodo.strftime("%Y-%m")
                agenda_key = pm.agenda.nome_agenda.strip().upper()
                prod_index[agenda_key][chave_mes] += pm.agend_totais
    else:
        # Fallback: usa ProducaoAgenda agregada (sem filtro por médico)
        for ag in ProducaoAgenda.objects.filter(upload__in=uploads_no_range).select_related("upload"):
            chave_mes  = ag.upload.data_inicio_periodo.strftime("%Y-%m")
            agenda_key = ag.nome_agenda.strip().upper()
            prod_index[agenda_key][chave_mes] += ag.agend_totais

    # ── Montar séries por serviço contratado ─────────────────────────────────
    tipo_labels = {
        "consulta":        "Consulta Ambulatorial",
        "cirurgia_pequeno":"Cirurgia de Pequeno Porte",
        "cirurgia_medio":  "Cirurgia de Médio Porte",
        "exame":           "Exame / Laudo",
        "outro":           "Outro",
    }

    series = []
    for srv in servicos:
        descricao_key = srv.descricao.strip().upper()
        producao_por_mes = [
            prod_index[descricao_key].get(chave, 0)
            for chave in chaves
        ]
        series.append({
            "id":          srv.pk,
            "descricao":   srv.descricao or srv.get_tipo_servico_display(),
            "tipo_label":  tipo_labels.get(srv.tipo_servico, srv.tipo_servico),
            "meta_fixa":   srv.quantidade_estimada_mes,
            "producao":    producao_por_mes,
            "medicos":     sorted(medicos_do_prestador),
        })

    periodo_label = (
        f"{periodos_no_range[0][1]} – {periodos_no_range[-1][1]}"
        if periodos_no_range else "—"
    )

    return render(request, "cadastro/indicadores_prestador.html", {
        **ctx_base,
        "prestador_selecionado": prestador_pk,
        "prestador_obj": prestador_obj,
        "series": series,
        "series_json": json.dumps(series, ensure_ascii=False),
        "labels_json": json.dumps(labels, ensure_ascii=False),
        "periodo_label": periodo_label,
        "aviso_sem_medicos": aviso_sem_medicos,
        "medicos_do_prestador": sorted(medicos_do_prestador),
    })


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
