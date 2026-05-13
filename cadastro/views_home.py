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

    Filtros GET:
      prestador      — pk do Prestador
      especialidade  — pk da Especialidade
      mes_ini        — "AAAA-MM"
      mes_fim        — "AAAA-MM"
      agenda         — nome da agenda (filtro de gráfico)
      medico         — nome do médico em UPPER (filtro de gráfico)
    """
    import json, calendar
    from datetime import date
    from collections import defaultdict

    from .models import (
        Prestador, Especialidade, Medico,
        ServicoContratado, UploadProducao,
        ProducaoAgenda, ProducaoMedico, AgendaMapeamento,
    )

    prestadores    = Prestador.objects.filter(ativo=True).order_by("nome_empresa")
    especialidades = Especialidade.objects.filter(ativa=True).order_by("nome")

    prestador_pk     = request.GET.get("prestador", "")
    especialidade_pk = request.GET.get("especialidade", "")
    mes_ini_str      = request.GET.get("mes_ini", "")
    mes_fim_str      = request.GET.get("mes_fim", "")
    filtro_agenda    = request.GET.get("agenda", "").strip()
    filtro_medico    = request.GET.get("medico", "").strip().upper()

    # ── Opções de mês (deduplica por chave) ─────────────────────────────────
    uploads_qs = UploadProducao.objects.filter(
        status="confirmado", data_inicio_periodo__isnull=False,
    ).order_by("data_inicio_periodo")

    periodos_disponiveis, seen = [], set()
    for u in uploads_qs:
        chave = u.data_inicio_periodo.strftime("%Y-%m")
        if chave not in seen:
            seen.add(chave)
            periodos_disponiveis.append((chave, u.data_inicio_periodo.strftime("%b/%Y").capitalize()))

    if not periodos_disponiveis:
        hoje = date.today()
        for i in range(11, -1, -1):
            m, y = hoje.month - i, hoje.year
            while m <= 0: m += 12; y -= 1
            periodos_disponiveis.append((f"{y}-{m:02d}", f"{calendar.month_abbr[m]}/{y}".capitalize()))

    mes_ini_sel = mes_ini_str or (periodos_disponiveis[0][0] if periodos_disponiveis else date.today().strftime("%Y-%m"))
    mes_fim_sel = mes_fim_str or (periodos_disponiveis[-1][0] if periodos_disponiveis else date.today().strftime("%Y-%m"))

    ctx_base = {
        "prestadores": prestadores,
        "especialidades": especialidades,
        "meses_opcoes": periodos_disponiveis,
        "mes_ini_selecionado": mes_ini_sel,
        "mes_fim_selecionado": mes_fim_sel,
        "especialidade_selecionada": especialidade_pk,
        "filtro_agenda": filtro_agenda,
        "filtro_medico": filtro_medico,
    }

    if not prestador_pk:
        return render(request, "cadastro/indicadores_prestador.html", {
            **ctx_base,
            "prestador_selecionado": "",
            "prestador_obj": None,
            "series": [], "series_json": "[]", "labels_json": "[]",
            "periodo_label": "", "aviso_sem_medicos": False,
            "medicos_disponiveis": [], "agendas_disponiveis": [],
        })

    prestador_obj = get_object_or_404(Prestador, pk=prestador_pk, ativo=True)

    # ── Serviços contratados ─────────────────────────────────────────────────
    servicos_qs = ServicoContratado.objects.filter(prestador=prestador_obj).select_related("especialidade")
    if especialidade_pk:
        servicos_qs = servicos_qs.filter(especialidade__pk=especialidade_pk)
    servicos = list(servicos_qs)

    # ── Intervalo de períodos ────────────────────────────────────────────────
    periodos_no_range = [
        (chave, label) for chave, label in periodos_disponiveis
        if mes_ini_sel <= chave <= mes_fim_sel
    ] or periodos_disponiveis

    labels = [label for _, label in periodos_no_range]
    chaves = [chave for chave, _ in periodos_no_range]

    ini_global = date(int(chaves[0][:4]), int(chaves[0][5:]), 1)
    fim_global  = date(
        int(chaves[-1][:4]), int(chaves[-1][5:]),
        calendar.monthrange(int(chaves[-1][:4]), int(chaves[-1][5:]))[1],
    )

    # ── Upload representativo por mês (o mais recente de cada mês) ───────────
    # Evita acumulação quando há múltiplos uploads para o mesmo mês
    upload_por_mes = {}  # chave_mes → upload_pk mais recente
    for u in UploadProducao.objects.filter(
        status="confirmado",
        data_inicio_periodo__gte=ini_global,
        data_inicio_periodo__lte=fim_global,
    ).order_by("data_inicio_periodo", "-enviado_em"):
        chave = u.data_inicio_periodo.strftime("%Y-%m")
        if chave not in upload_por_mes:   # order_by enviado_em desc → primeiro = mais recente
            upload_por_mes[chave] = u.pk

    uploads_representativos = list(upload_por_mes.values())

    # ── Médicos do prestador ─────────────────────────────────────────────────
    medicos_do_prestador = sorted(
        Medico.objects.filter(prestador=prestador_obj, ativo=True)
        .values_list("nome_completo", flat=True)
    )
    nomes_upper = {n.strip().upper() for n in medicos_do_prestador}
    aviso_sem_medicos = len(nomes_upper) == 0

    # ── Construir índice de produção ─────────────────────────────────────────
    # { agenda_upper: { chave_mes: { medico_upper: valor } } }
    # Granularidade por médico para permitir filtro posterior
    prod_index = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    if nomes_upper:
        for pm in ProducaoMedico.objects.filter(
            agenda__upload__in=uploads_representativos,
        ).select_related("agenda__upload"):
            nome_up = pm.nome_medico.strip().upper()
            if nome_up not in nomes_upper:
                continue
            chave_mes  = pm.agenda.upload.data_inicio_periodo.strftime("%Y-%m")
            agenda_key = pm.agenda.nome_agenda.strip().upper()
            prod_index[agenda_key][chave_mes][nome_up] += pm.agend_totais
    else:
        for ag in ProducaoAgenda.objects.filter(
            upload__in=uploads_representativos,
        ).select_related("upload"):
            chave_mes  = ag.upload.data_inicio_periodo.strftime("%Y-%m")
            agenda_key = ag.nome_agenda.strip().upper()
            prod_index[agenda_key][chave_mes]["__total__"] += ag.agend_totais

    # ── Listas para filtros dinâmicos ────────────────────────────────────────
    agendas_disponiveis = sorted({
        ag for ag in prod_index.keys()
    })
    medicos_disponiveis = sorted(medicos_do_prestador)

    # ── Mapeamentos ──────────────────────────────────────────────────────────
    mapeamentos_por_servico = defaultdict(list)
    for srv_pk, nome in AgendaMapeamento.objects.filter(
        servico__prestador=prestador_obj
    ).values_list("servico_id", "nome_agenda"):
        mapeamentos_por_servico[srv_pk].append(nome.strip().upper())

    # ── Montar séries ────────────────────────────────────────────────────────
    tipo_labels = {
        "consulta": "Consulta", "cirurgia_pequeno": "Cirurgia P. Porte",
        "cirurgia_medio": "Cirurgia M. Porte", "exame": "Exame / Laudo", "outro": "Outro",
    }

    # Filtro de agenda aplicado ao conjunto de chaves_agenda
    def filtrar_agendas(chaves_ag):
        if filtro_agenda:
            return [k for k in chaves_ag if filtro_agenda.upper() in k]
        return chaves_ag

    # Filtro de médico aplicado ao somar o índice
    def somar_mes(agenda_key, chave_mes):
        medicos_mes = prod_index[agenda_key].get(chave_mes, {})
        if filtro_medico:
            return sum(v for k, v in medicos_mes.items() if filtro_medico in k)
        return sum(medicos_mes.values())

    series = []
    for srv in servicos:
        chaves_agenda = mapeamentos_por_servico.get(srv.pk) or [srv.descricao.strip().upper()]
        chaves_agenda = filtrar_agendas(chaves_agenda)

        producao_por_mes = [
            sum(somar_mes(ag_key, chave) for ag_key in chaves_agenda)
            for chave in chaves
        ]

        agendas_mapeadas = [
            m.nome_agenda for m in AgendaMapeamento.objects.filter(servico=srv).order_by("nome_agenda")
        ] or [srv.descricao]

        series.append({
            "id": srv.pk,
            "descricao":      srv.descricao or srv.get_tipo_servico_display(),
            "tipo_label":     tipo_labels.get(srv.tipo_servico, srv.tipo_servico),
            "meta_fixa":      srv.quantidade_estimada_mes,
            "producao":       producao_por_mes,
            "agendas_mapeadas": agendas_mapeadas,
            "tem_mapeamento": bool(mapeamentos_por_servico.get(srv.pk)),
        })

    periodo_label = (
        f"{periodos_no_range[0][1]} – {periodos_no_range[-1][1]}" if periodos_no_range else "—"
    )

    return render(request, "cadastro/indicadores_prestador.html", {
        **ctx_base,
        "prestador_selecionado": prestador_pk,
        "prestador_obj": prestador_obj,
        "series": series,
        "series_json":  json.dumps(series, ensure_ascii=False),
        "labels_json":  json.dumps(labels, ensure_ascii=False),
        "periodo_label": periodo_label,
        "aviso_sem_medicos": aviso_sem_medicos,
        "medicos_do_prestador": medicos_do_prestador,
        "medicos_disponiveis":  medicos_disponiveis,
        "agendas_disponiveis":  agendas_disponiveis,
    })



def indicadores_especialidade(request):
    """
    Dashboard de produção por especialidade — independente de prestador.
    Agrega ProducaoMedico de todos os médicos de uma especialidade,
    cruzando via Medico.especialidades (M2M).
    """
    import json, calendar
    from datetime import date
    from collections import defaultdict

    from .models import (
        Especialidade, Medico, UploadProducao,
        ProducaoMedico, ProducaoAgenda, AgendaMapeamento,
    )

    especialidades    = Especialidade.objects.filter(ativa=True).order_by("nome")
    especialidade_pk  = request.GET.get("especialidade", "")
    mes_ini_str       = request.GET.get("mes_ini", "")
    mes_fim_str       = request.GET.get("mes_fim", "")
    filtro_medico     = request.GET.get("medico", "").strip().upper()

    # ── Opções de mês ────────────────────────────────────────────────────────
    uploads_qs = UploadProducao.objects.filter(
        status="confirmado", data_inicio_periodo__isnull=False,
    ).order_by("data_inicio_periodo")

    periodos_disponiveis, seen = [], set()
    for u in uploads_qs:
        chave = u.data_inicio_periodo.strftime("%Y-%m")
        if chave not in seen:
            seen.add(chave)
            periodos_disponiveis.append((chave, u.data_inicio_periodo.strftime("%b/%Y").capitalize()))

    mes_ini_sel = mes_ini_str or (periodos_disponiveis[0][0]  if periodos_disponiveis else date.today().strftime("%Y-%m"))
    mes_fim_sel = mes_fim_str or (periodos_disponiveis[-1][0] if periodos_disponiveis else date.today().strftime("%Y-%m"))

    ctx_base = {
        "especialidades": especialidades,
        "meses_opcoes": periodos_disponiveis,
        "mes_ini_selecionado": mes_ini_sel,
        "mes_fim_selecionado": mes_fim_sel,
        "especialidade_selecionada": especialidade_pk,
        "filtro_medico": filtro_medico,
    }

    if not especialidade_pk:
        return render(request, "cadastro/indicadores_especialidade.html", {
            **ctx_base,
            "especialidade_obj": None,
            "series": [], "series_json": "[]", "labels_json": "[]",
            "periodo_label": "", "medicos_disponiveis": [],
        })

    especialidade_obj = get_object_or_404(Especialidade, pk=especialidade_pk)

    # ── Intervalo ────────────────────────────────────────────────────────────
    periodos_no_range = [
        (c, l) for c, l in periodos_disponiveis if mes_ini_sel <= c <= mes_fim_sel
    ] or periodos_disponiveis

    labels = [l for _, l in periodos_no_range]
    chaves = [c for c, _ in periodos_no_range]

    ini_global = date(int(chaves[0][:4]), int(chaves[0][5:]), 1)
    fim_global  = date(
        int(chaves[-1][:4]), int(chaves[-1][5:]),
        calendar.monthrange(int(chaves[-1][:4]), int(chaves[-1][5:]))[1],
    )

    # Upload representativo por mês (mais recente)
    upload_por_mes = {}
    for u in UploadProducao.objects.filter(
        status="confirmado",
        data_inicio_periodo__gte=ini_global,
        data_inicio_periodo__lte=fim_global,
    ).order_by("data_inicio_periodo", "-enviado_em"):
        chave = u.data_inicio_periodo.strftime("%Y-%m")
        if chave not in upload_por_mes:
            upload_por_mes[chave] = u.pk

    uploads_rep = list(upload_por_mes.values())

    # ── Médicos desta especialidade ──────────────────────────────────────────
    medicos_esp = Medico.objects.filter(
        especialidades=especialidade_obj, ativo=True,
    ).values_list("nome_completo", flat=True)
    nomes_upper = {n.strip().upper() for n in medicos_esp}
    medicos_disponiveis = sorted(medicos_esp)

    # ── Índice de produção: { agenda_upper: { chave_mes: { medico: val } } } ─
    prod_index = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    if nomes_upper:
        for pm in ProducaoMedico.objects.filter(
            agenda__upload__in=uploads_rep,
        ).select_related("agenda__upload"):
            nome_up = pm.nome_medico.strip().upper()
            if nome_up not in nomes_upper:
                continue
            chave_mes  = pm.agenda.upload.data_inicio_periodo.strftime("%Y-%m")
            agenda_key = pm.agenda.nome_agenda.strip().upper()
            prod_index[agenda_key][chave_mes][nome_up] += pm.agend_totais
    else:
        # Sem médicos cadastrados: usa ProducaoAgenda para as agendas da especialidade
        for ag in ProducaoAgenda.objects.filter(upload__in=uploads_rep).select_related("upload"):
            chave_mes  = ag.upload.data_inicio_periodo.strftime("%Y-%m")
            agenda_key = ag.nome_agenda.strip().upper()
            prod_index[agenda_key][chave_mes]["__total__"] += ag.agend_totais

    # ── Agrupar por agenda (cada agenda = uma série / gráfico) ───────────────
    def somar_mes(agenda_key, chave_mes):
        medicos_mes = prod_index[agenda_key].get(chave_mes, {})
        if filtro_medico:
            return sum(v for k, v in medicos_mes.items() if filtro_medico in k)
        return sum(medicos_mes.values())

    agendas_com_dados = [ag for ag in sorted(prod_index.keys()) if any(
        somar_mes(ag, c) > 0 for c in chaves
    )]

    series = []
    for ag_key in agendas_com_dados:
        producao_por_mes = [somar_mes(ag_key, c) for c in chaves]
        series.append({
            "id":        ag_key,
            "descricao": ag_key.title(),
            "producao":  producao_por_mes,
            "meta_fixa": 0,           # sem meta quando visão é por especialidade
        })

    periodo_label = (
        f"{periodos_no_range[0][1]} – {periodos_no_range[-1][1]}" if periodos_no_range else "—"
    )

    return render(request, "cadastro/indicadores_especialidade.html", {
        **ctx_base,
        "especialidade_obj": especialidade_obj,
        "series": series,
        "series_json":  json.dumps(series, ensure_ascii=False),
        "labels_json":  json.dumps(labels, ensure_ascii=False),
        "periodo_label": periodo_label,
        "medicos_disponiveis": medicos_disponiveis,
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


def diagnostico_producao(request):
    """Rota temporária de diagnóstico — remover após resolver o problema."""
    from django.http import JsonResponse
    from .models import UploadProducao, ProducaoAgenda, ProducaoMedico, Prestador, Medico

    prestador_pk = request.GET.get("prestador", "")

    data = {
        "uploads": [],
        "amostra_agendas": [],
        "amostra_medicos_producao": [],
        "prestador": None,
        "medicos_cadastrados": [],
    }

    # Uploads
    for u in UploadProducao.objects.order_by("data_inicio_periodo")[:20]:
        data["uploads"].append({
            "pk": u.pk,
            "tipo": u.get_tipo_display(),
            "status": u.status,
            "periodo": str(u.data_inicio_periodo),
            "total_agendas": u.total_agendas,
            "total_medicos": u.total_medicos,
        })

    # Amostra de agendas
    for ag in ProducaoAgenda.objects.select_related("upload").order_by("upload__data_inicio_periodo")[:20]:
        data["amostra_agendas"].append({
            "periodo": str(ag.upload.data_inicio_periodo),
            "nome_agenda": ag.nome_agenda,
            "agend_totais": ag.agend_totais,
        })

    # Amostra de médicos na produção
    for pm in ProducaoMedico.objects.select_related("agenda__upload").order_by("agenda__upload__data_inicio_periodo")[:30]:
        data["amostra_medicos_producao"].append({
            "periodo": str(pm.agenda.upload.data_inicio_periodo),
            "nome_medico": pm.nome_medico,
            "agenda": pm.agenda.nome_agenda,
            "agend_totais": pm.agend_totais,
        })

    # Prestador e médicos cadastrados
    if prestador_pk:
        try:
            p = Prestador.objects.get(pk=prestador_pk)
            data["prestador"] = {
                "pk": p.pk,
                "nome": p.nome_empresa,
                "servicos": [{"descricao": s.descricao, "qtde_mes": s.quantidade_estimada_mes}
                             for s in p.servicos.all()],
            }
            data["medicos_cadastrados"] = [
                {"nome_completo": m.nome_completo, "nome_upper": m.nome_completo.strip().upper()}
                for m in Medico.objects.filter(prestador=p)
            ]
        except Prestador.DoesNotExist:
            data["prestador"] = "não encontrado"

    # Cruzamento: nomes de médicos cadastrados vs nomes na produção
    if data["medicos_cadastrados"] and data["amostra_medicos_producao"]:
        nomes_upper = {m["nome_upper"] for m in data["medicos_cadastrados"]}
        matches = [pm for pm in data["amostra_medicos_producao"]
                   if pm["nome_medico"].strip().upper() in nomes_upper]
        data["cruzamento_matches"] = matches
    else:
        data["cruzamento_matches"] = []

    # Busca específica por nome de médico na produção
    buscar_medico = request.GET.get("buscar_medico", "").strip().upper()
    if buscar_medico:
        matches = list(
            ProducaoMedico.objects
            .filter(nome_medico__icontains=buscar_medico)
            .select_related("agenda__upload")
            .values("nome_medico", "agenda__nome_agenda",
                    "agenda__upload__data_inicio_periodo", "agend_totais")
            .order_by("agenda__upload__data_inicio_periodo")[:50]
        )
        data["busca_medico"] = {
            "termo": buscar_medico,
            "total_encontrado": len(matches),
            "registros": [
                {
                    "periodo": str(m["agenda__upload__data_inicio_periodo"]),
                    "nome_medico": m["nome_medico"],
                    "agenda": m["agenda__nome_agenda"],
                    "agend_totais": m["agend_totais"],
                }
                for m in matches
            ],
        }

    return JsonResponse(data, json_dumps_params={"ensure_ascii": False, "indent": 2})
