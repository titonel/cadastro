from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Sum, F
from .models import Prestador, Especialidade, ContratoUpload, StatusImportacao
from .forms import PrestadorForm, ServicoFormSet, UploadContratoForm
from .extrator import extrair_contrato


# ─── Prestadores ───────────────────────────────────────────────────────────────────

def prestador_list(request):
    qs = Prestador.objects.prefetch_related("especialidades", "servicos")
    q = request.GET.get("q", "").strip()
    especialidade_id = request.GET.get("especialidade", "")
    ativo = request.GET.get("ativo", "")

    if q:
        qs = qs.filter(
            Q(nome_empresa__icontains=q)
            | Q(cnpj__icontains=q)
            | Q(nome_representante__icontains=q)
        )
    if especialidade_id:
        qs = qs.filter(especialidades__id=especialidade_id)
    if ativo in ("1", "0"):
        qs = qs.filter(ativo=ativo == "1")

    especialidades = Especialidade.objects.filter(ativa=True)
    context = {
        "prestadores": qs.distinct(),
        "especialidades": especialidades,
        "q": q,
        "especialidade_id": especialidade_id,
        "ativo": ativo,
    }
    return render(request, "cadastro/prestador_list.html", context)


def prestador_detail(request, pk):
    prestador = get_object_or_404(
        Prestador.objects.prefetch_related("especialidades", "servicos__especialidade"), pk=pk
    )
    valor_mensal = prestador.servicos.aggregate(
        total=Sum(F("quantidade_estimada_mes") * F("valor_unitario"))
    )["total"] or 0
    meses = 0
    if prestador.data_inicio_contrato and prestador.data_fim_contrato:
        delta = prestador.data_fim_contrato - prestador.data_inicio_contrato
        meses = round(delta.days / 30.44)
    valor_global = valor_mensal * meses
    context = {
        "prestador": prestador,
        "valor_mensal": valor_mensal,
        "valor_global": valor_global,
        "meses_vigencia": meses,
    }
    return render(request, "cadastro/prestador_detail.html", context)


def prestador_create(request):
    if request.method == "POST":
        form = PrestadorForm(request.POST)
        formset = ServicoFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            prestador = form.save()
            formset.instance = prestador
            formset.save()
            messages.success(request, f"Prestador \u201c{prestador.nome_empresa}\u201d cadastrado com sucesso.")
            return redirect("cadastro:prestador_detail", pk=prestador.pk)
    else:
        form = PrestadorForm()
        formset = ServicoFormSet()
    return render(request, "cadastro/prestador_form.html", {"form": form, "formset": formset, "action": "Novo"})


def prestador_edit(request, pk):
    prestador = get_object_or_404(Prestador, pk=pk)
    if request.method == "POST":
        form = PrestadorForm(request.POST, instance=prestador)
        formset = ServicoFormSet(request.POST, instance=prestador)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f"Prestador \u201c{prestador.nome_empresa}\u201d atualizado.")
            return redirect("cadastro:prestador_detail", pk=prestador.pk)
    else:
        form = PrestadorForm(instance=prestador)
        formset = ServicoFormSet(instance=prestador)
    return render(request, "cadastro/prestador_form.html", {"form": form, "formset": formset, "action": "Editar", "prestador": prestador})


def prestador_delete(request, pk):
    prestador = get_object_or_404(Prestador, pk=pk)
    if request.method == "POST":
        nome = prestador.nome_empresa
        prestador.delete()
        messages.success(request, f"Prestador \u201c{nome}\u201d removido.")
        return redirect("cadastro:prestador_list")
    return render(request, "cadastro/prestador_confirm_delete.html", {"prestador": prestador})


# ─── Helpers ───────────────────────────────────────────────────────────────────────────

def _resolver_especialidade(nome_extraido: str) -> list:
    if not nome_extraido:
        return []
    nome = nome_extraido.strip()
    esp = Especialidade.objects.filter(nome__iexact=nome).first()
    if not esp:
        for token in nome.split():
            if len(token) >= 5:
                esp = Especialidade.objects.filter(nome__icontains=token).first()
                if esp:
                    break
    if not esp:
        esp = Especialidade.objects.create(nome=nome, ativa=True)
    return [esp]


def _title_case_nome(nome: str) -> str:
    """Converte nome em MAIÚSCULAS para Title Case, preservando partículas."""
    if not nome:
        return nome
    particulas = {"de", "da", "do", "das", "dos", "e", "em", "na", "no", "nas", "nos"}
    palavras = nome.strip().split()
    resultado = []
    for i, p in enumerate(palavras):
        lower = p.lower()
        if i > 0 and lower in particulas:
            resultado.append(lower)
        else:
            resultado.append(p.capitalize())
    return " ".join(resultado)


def _prazo_para_dias(prazo_str: str) -> int:
    import re
    if not prazo_str:
        return 0
    m = re.search(r"(\d+)", prazo_str)
    return int(m.group(1)) if m else 0


def _montar_initial_formset(servicos_tabela: list, servicos_anexo1: list) -> list:
    """
    Combina a tabela financeira (3.1) com os prazos do Anexo 1 para gerar
    o initial data do ServicoFormSet (seção 8).
    """
    prazos = {}
    for s in servicos_anexo1:
        chave = s.get("exame", "").strip().lower()
        prazos[chave] = _prazo_para_dias(s.get("prazo_entrega", ""))

    initial = []
    for s in servicos_tabela:
        nome = s.get("descricao", "")
        chave = nome.strip().lower()
        prazo_dias = prazos.get(chave, 0)
        initial.append({
            "descricao": nome,
            "tipo_servico": "exame",
            "unidade_medida": "Exame",
            "quantidade_estimada_mes": s.get("quantidade", 0),
            "valor_unitario": s.get("valor_unitario", 0.0),
            "prazo_entrega_laudo_dias": prazo_dias or None,
        })
    return initial


# ─── Upload / Importação de Contratos ──────────────────────────────────────────────────

def contrato_upload(request):
    """Recebe o PDF, extrai os dados e redireciona para a tela de revisão."""
    if request.method == "POST":
        form = UploadContratoForm(request.POST, request.FILES)
        if form.is_valid():
            contrato = form.save(commit=False)
            contrato.nome_arquivo = request.FILES["arquivo"].name
            contrato.save()

            dados = extrair_contrato(contrato.arquivo.path)

            contrato.razao_social_extraida    = dados["razao_social"]
            contrato.cnpj_extraido            = dados["cnpj"]
            contrato.objeto_extraido          = dados["objeto"]
            contrato.servicos_extraidos       = dados["servicos"]
            contrato.especialidade_extraida   = dados["especialidade"]
            contrato.data_inicio_extraida     = dados["data_assinatura"]
            contrato.data_fim_extraida        = dados["data_fim"]
            contrato.meses_vigencia_extraidos = dados["meses_vigencia"]
            contrato.valor_mensal_extraido    = dados["valor_mensal"]
            contrato.valor_global_extraido    = dados["valor_global"]
            contrato.numero_processo_extraido = dados["numero_processo"]
            contrato.erro_extracao            = dados["erro"] or ""

            if dados["erro"]:
                contrato.status = StatusImportacao.ERRO
            contrato.save()

            # Persiste todos os campos extras (não mapeados no model) na sessão
            request.session[f"imp_{contrato.pk}"] = {
                "nome_representante":   _title_case_nome(dados.get("nome_representante", "")),
                "cpf_representante":    dados.get("cpf_representante", ""),
                "inscricao_municipal":  dados.get("inscricao_municipal", ""),
                "logradouro":           dados.get("logradouro", ""),
                "numero":               dados.get("numero", ""),
                "complemento":          dados.get("complemento", ""),
                "bairro":               dados.get("bairro", ""),
                "cep":                  dados.get("cep", ""),
                "cidade":               dados.get("cidade", ""),
                "servicos_contratados": dados.get("servicos_contratados", []),
            }

            return redirect("cadastro:contrato_revisao", pk=contrato.pk)
    else:
        form = UploadContratoForm()

    importacoes = ContratoUpload.objects.all()[:20]
    return render(request, "cadastro/contrato_upload.html", {"form": form, "importacoes": importacoes})


def contrato_revisao(request, pk):
    """Exibe os dados extraídos para revisão e permite confirmar o cadastro."""
    contrato = get_object_or_404(ContratoUpload, pk=pk)

    # Recupera dados extras da sessão (descartados após leitura)
    extras = request.session.pop(f"imp_{contrato.pk}", {})

    especialidades_iniciais = _resolver_especialidade(contrato.especialidade_extraida)

    initial = {
        # Seção 1 – Dados da Empresa
        "nome_empresa":        contrato.razao_social_extraida,
        "cnpj":                contrato.cnpj_extraido,
        "inscricao_municipal": extras.get("inscricao_municipal", ""),
        # Seção 2 – Endereço
        "logradouro":          extras.get("logradouro", ""),
        "numero":              extras.get("numero", ""),
        "complemento":         extras.get("complemento", ""),
        "bairro":              extras.get("bairro", ""),
        "cep":                 extras.get("cep", ""),
        "cidade":              extras.get("cidade", ""),
        # Seção 4 – Representante Legal
        "nome_representante":  extras.get("nome_representante", ""),
        "cpf_representante":   extras.get("cpf_representante",  ""),
        # Seção 6 – Especialidades
        "especialidades":      especialidades_iniciais,
        # Seção 7 – Vigência
        "data_inicio_contrato": contrato.data_inicio_extraida,
        "data_fim_contrato":    contrato.data_fim_extraida,
        "numero_processo":      contrato.numero_processo_extraido,
    }

    # Monta initial do formset a partir dos serviços extraídos
    servicos_tabela = contrato.servicos_extraidos or []
    servicos_anexo1 = extras.get("servicos_contratados", [])
    formset_initial = _montar_initial_formset(servicos_tabela, servicos_anexo1)

    if request.method == "POST":
        form = PrestadorForm(request.POST)
        formset = ServicoFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            prestador = form.save()
            # Salva M2M manualmente (necessário pois commit=True por padrão)
            especialidades_post = request.POST.getlist("especialidades")
            if especialidades_post:
                prestador.especialidades.set(especialidades_post)
            formset.instance = prestador
            formset.save()
            contrato.prestador = prestador
            contrato.status    = StatusImportacao.CONFIRMADO
            contrato.save()
            messages.success(
                request,
                f"Prestador \u201c{prestador.nome_empresa}\u201d cadastrado a partir do contrato importado."
            )
            return redirect("cadastro:prestador_detail", pk=prestador.pk)
    else:
        form = PrestadorForm(initial=initial)
        if especialidades_iniciais:
            form.fields["especialidades"].initial = especialidades_iniciais

        # Seção 8 – pré-popula o formset com extra=len(initial) para mostrar as linhas
        from django.forms import inlineformset_factory
        from .models import ServicoContratado
        from .forms import ServicoFormSet as _BaseFormSet
        n = max(len(formset_initial), 1)
        FormSetComExtra = inlineformset_factory(
            Prestador,
            ServicoContratado,
            fields=[
                "especialidade", "tipo_servico", "descricao", "unidade_medida",
                "quantidade_estimada_mes", "valor_unitario",
                "prazo_entrega_laudo_dias", "remoto", "observacoes",
            ],
            extra=n,
            can_delete=True,
        )
        formset = FormSetComExtra(initial=formset_initial)

    return render(request, "cadastro/contrato_revisao.html", {
        "contrato":         contrato,
        "form":             form,
        "formset":          formset,
        "servicos_tabela":  servicos_tabela,
        "servicos_anexo1":  servicos_anexo1,
    })


def contrato_ignorar(request, pk):
    contrato = get_object_or_404(ContratoUpload, pk=pk)
    contrato.status = StatusImportacao.IGNORADO
    contrato.save()
    messages.info(request, "Importação marcada como ignorada.")
    return redirect("cadastro:contrato_upload")


# ── Módulo: Cadastro de Médicos ───────────────────────────────────────────────

from .models import Medico
from .forms import MedicoForm


def medico_list(request):
    qs = Medico.objects.select_related("prestador").prefetch_related("especialidades")

    q = request.GET.get("q", "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(nome_completo__icontains=q) |
            Q(crm__icontains=q) |
            Q(cpf__icontains=q)
        )

    esp_pk = request.GET.get("especialidade", "")
    if esp_pk:
        qs = qs.filter(especialidades__pk=esp_pk)

    prestador_pk = request.GET.get("prestador", "")
    if prestador_pk:
        qs = qs.filter(prestador__pk=prestador_pk)

    from .models import Especialidade, Prestador
    return render(request, "cadastro/medico_list.html", {
        "medicos": qs,
        "q": q,
        "especialidades": Especialidade.objects.filter(ativa=True),
        "prestadores": Prestador.objects.filter(ativo=True),
        "especialidade_selecionada": esp_pk,
        "prestador_selecionado": prestador_pk,
    })


def medico_detail(request, pk):
    medico = get_object_or_404(Medico, pk=pk)
    return render(request, "cadastro/medico_detail.html", {"medico": medico})


def medico_create(request):
    if request.method == "POST":
        form = MedicoForm(request.POST, request.FILES)
        if form.is_valid():
            medico = form.save()
            messages.success(request, f"Médico {medico.nome_completo} cadastrado com sucesso.")
            return redirect("cadastro:medico_detail", pk=medico.pk)
    else:
        form = MedicoForm()
    return render(request, "cadastro/medico_form.html", {"form": form, "action": "Novo"})


def medico_edit(request, pk):
    medico = get_object_or_404(Medico, pk=pk)
    if request.method == "POST":
        form = MedicoForm(request.POST, request.FILES, instance=medico)
        if form.is_valid():
            form.save()
            messages.success(request, "Cadastro atualizado.")
            return redirect("cadastro:medico_detail", pk=medico.pk)
    else:
        form = MedicoForm(instance=medico)
    return render(request, "cadastro/medico_form.html", {"form": form, "action": "Editar", "medico": medico})


def medico_delete(request, pk):
    medico = get_object_or_404(Medico, pk=pk)
    if request.method == "POST":
        nome = medico.nome_completo
        medico.delete()
        messages.success(request, f"Médico {nome} removido.")
        return redirect("cadastro:medico_list")
    return render(request, "cadastro/medico_confirm_delete.html", {"medico": medico})
