from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Sum, F
from .models import Prestador, ServicoContratado, Especialidade, ContratoUpload, StatusImportacao
from .forms import PrestadorForm, ServicoFormSet, UploadContratoForm
from .extrator import extrair_contrato


# ─── Prestadores ────────────────────────────────────────────────────────────

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


# ─── Upload / Importação de Contratos ───────────────────────────────────────

def contrato_upload(request):
    """Recebe o PDF, extrai os dados e redireciona para a tela de revisão."""
    if request.method == "POST":
        form = UploadContratoForm(request.POST, request.FILES)
        if form.is_valid():
            contrato = form.save(commit=False)
            contrato.nome_arquivo = request.FILES["arquivo"].name
            contrato.save()

            # Extração
            dados = extrair_contrato(contrato.arquivo.path)

            contrato.razao_social_extraida = dados["razao_social"]
            contrato.cnpj_extraido = dados["cnpj"]
            contrato.objeto_extraido = dados["objeto"]
            contrato.servicos_extraidos = dados["servicos"]
            contrato.especialidade_extraida = dados["especialidade"]
            contrato.data_inicio_extraida = dados["data_assinatura"]
            contrato.data_fim_extraida = dados["data_fim"]
            contrato.meses_vigencia_extraidos = dados["meses_vigencia"]
            contrato.valor_mensal_extraido = dados["valor_mensal"]
            contrato.valor_global_extraido = dados["valor_global"]
            contrato.numero_processo_extraido = dados["numero_processo"]
            contrato.erro_extracao = dados["erro"] or ""

            if dados["erro"]:
                contrato.status = StatusImportacao.ERRO
            contrato.save()

            return redirect("cadastro:contrato_revisao", pk=contrato.pk)
    else:
        form = UploadContratoForm()

    # Lista de importações anteriores
    importacoes = ContratoUpload.objects.all()[:20]
    return render(request, "cadastro/contrato_upload.html", {"form": form, "importacoes": importacoes})


def contrato_revisao(request, pk):
    """Exibe os dados extraídos para revisão. Permite confirmar e criar o Prestador."""
    contrato = get_object_or_404(ContratoUpload, pk=pk)

    # Pré-preenche o form com os dados extraídos
    initial = {
        "nome_empresa": contrato.razao_social_extraida,
        "cnpj": contrato.cnpj_extraido,
        "data_inicio_contrato": contrato.data_inicio_extraida,
        "data_fim_contrato": contrato.data_fim_extraida,
        "numero_processo": contrato.numero_processo_extraido,
    }

    if request.method == "POST":
        form = PrestadorForm(request.POST)
        formset = ServicoFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            prestador = form.save()
            formset.instance = prestador
            formset.save()
            contrato.prestador = prestador
            contrato.status = StatusImportacao.CONFIRMADO
            contrato.save()
            messages.success(
                request,
                f"Prestador \u201c{prestador.nome_empresa}\u201d cadastrado a partir do contrato importado."
            )
            return redirect("cadastro:prestador_detail", pk=prestador.pk)
    else:
        form = PrestadorForm(initial=initial)
        # Pré-preenche o formset com os serviços extraídos
        formset = ServicoFormSet()

    return render(request, "cadastro/contrato_revisao.html", {
        "contrato": contrato,
        "form": form,
        "formset": formset,
    })


def contrato_ignorar(request, pk):
    contrato = get_object_or_404(ContratoUpload, pk=pk)
    contrato.status = StatusImportacao.IGNORADO
    contrato.save()
    messages.info(request, "Importação marcada como ignorada.")
    return redirect("cadastro:contrato_upload")
