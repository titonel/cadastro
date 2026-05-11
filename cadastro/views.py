from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Sum, F
from .models import Prestador, ServicoContratado, Especialidade
from .forms import PrestadorForm, ServicoFormSet


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
    prestador = get_object_or_404(Prestador.objects.prefetch_related("especialidades", "servicos__especialidade"), pk=pk)
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
