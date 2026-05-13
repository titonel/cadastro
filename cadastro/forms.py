from django import forms
from django.forms import inlineformset_factory
from .models import Prestador, ServicoContratado, Especialidade, ContratoUpload, Medico


class PrestadorForm(forms.ModelForm):
    especialidades = forms.ModelMultipleChoiceField(
        queryset=Especialidade.objects.filter(ativa=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Especialidades Médicas",
    )

    class Meta:
        model = Prestador
        fields = [
            "nome_empresa", "cnpj", "inscricao_municipal", "inscricao_estadual",
            "logradouro", "numero", "complemento", "bairro", "cidade", "estado", "cep",
            "telefone", "email",
            "nome_representante", "cpf_representante", "crm_representante",
            "nome_testemunha", "telefone_testemunha", "email_testemunha",
            "especialidades",
            "data_inicio_contrato", "data_fim_contrato", "numero_processo",
            "ativo",
        ]
        widgets = {
            "data_inicio_contrato": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_fim_contrato": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "cnpj":              forms.TextInput(attrs={"placeholder": "00.000.000/0000-00", "data-mask": "cnpj",     "maxlength": "18"}),
            "cpf_representante": forms.TextInput(attrs={"placeholder": "000.000.000-00",    "data-mask": "cpf",      "maxlength": "14"}),
            "cep":               forms.TextInput(attrs={"placeholder": "00000-000",          "data-mask": "cep",      "maxlength": "9"}),
            "telefone":          forms.TextInput(attrs={"placeholder": "11-99999-9999",      "data-mask": "telefone", "maxlength": "13"}),
            "telefone_testemunha": forms.TextInput(attrs={"placeholder": "11-99999-9999",    "data-mask": "telefone", "maxlength": "13"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Torna todos os campos opcionais para permitir salvamento parcial
        campos_obrigatorios = {"nome_empresa", "cnpj"}
        for name, field in self.fields.items():
            if name not in campos_obrigatorios:
                field.required = False
                # Remove validadores de formato em campos opcionais para não bloquear vazios
                if hasattr(field, 'validators'):
                    field.validators = [
                        v for v in field.validators
                        if name in campos_obrigatorios
                    ]
            if isinstance(field.widget, (forms.TextInput, forms.EmailInput, forms.Select, forms.DateInput)):
                field.widget.attrs.setdefault("class", "form-control")
            elif isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs.setdefault("class", "checkbox-list")
        self.fields["data_inicio_contrato"].input_formats = ["%Y-%m-%d"]
        self.fields["data_fim_contrato"].input_formats = ["%Y-%m-%d"]

    @staticmethod
    def _so_digitos(valor):
        import re
        return re.sub(r"\D", "", valor or "")

    def clean_cnpj(self):
        return self._so_digitos(self.cleaned_data.get("cnpj", ""))

    def clean_cpf_representante(self):
        return self._so_digitos(self.cleaned_data.get("cpf_representante", ""))

    def clean_cep(self):
        return self._so_digitos(self.cleaned_data.get("cep", ""))

    def clean_telefone(self):
        return self._so_digitos(self.cleaned_data.get("telefone", ""))

    def clean_telefone_testemunha(self):
        return self._so_digitos(self.cleaned_data.get("telefone_testemunha", ""))


ServicoFormSet = inlineformset_factory(
    Prestador,
    ServicoContratado,
    fields=[
        "especialidade", "tipo_servico", "descricao", "unidade_medida",
        "quantidade_estimada_mes", "valor_unitario",
        "prazo_entrega_laudo_dias", "remoto", "observacoes",
    ],
    extra=1,          # sempre exibe ao menos uma linha vazia para adicionar serviços
    can_delete=True,
    widgets={
        "descricao": forms.TextInput(attrs={"class": "form-control"}),
        "unidade_medida": forms.TextInput(attrs={"class": "form-control"}),
        "quantidade_estimada_mes": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        "valor_unitario": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": 0}),
        "prazo_entrega_laudo_dias": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
        "tipo_servico": forms.Select(attrs={"class": "form-control"}),
        "especialidade": forms.Select(attrs={"class": "form-control"}),
        "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    },
)


class UploadContratoForm(forms.ModelForm):
    class Meta:
        model = ContratoUpload
        fields = ["arquivo"]
        widgets = {
            "arquivo": forms.FileInput(attrs={
                "accept": ".pdf",
                "class": "form-control",
                "id": "arquivo-pdf",
            })
        }
        labels = {
            "arquivo": "Arquivo PDF do Contrato"
        }


class MedicoForm(forms.ModelForm):
    especialidades = forms.ModelMultipleChoiceField(
        queryset=Especialidade.objects.filter(ativa=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Especialidades no AME",
    )

    class Meta:
        model = Medico
        fields = [
            "nome_completo", "cpf", "crm", "rqe", "foto",
            "telefone", "email",
            "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "estado",
            "especialidades", "prestador",
            "ativo",
        ]
        widgets = {
            "cpf":      forms.TextInput(attrs={"placeholder": "000.000.000-00",   "data-mask": "cpf",      "maxlength": "14"}),
            "cep":      forms.TextInput(attrs={"placeholder": "00000-000",           "data-mask": "cep",      "maxlength": "9",  "id": "id_cep_medico"}),
            "telefone": forms.TextInput(attrs={"placeholder": "11-99999-9999",       "data-mask": "telefone", "maxlength": "13"}),
            "foto":     forms.FileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Prestador
        self.fields["prestador"].queryset = Prestador.objects.filter(ativo=True).order_by("nome_empresa")
        self.fields["prestador"].empty_label = "— selecione —"
        self.fields["prestador"].required = False

        for name, field in self.fields.items():
            if name in ("especialidades",):
                continue
            if name == "ativo":
                continue
            field.required = name == "nome_completo"
            widget = field.widget
            if isinstance(widget, (forms.TextInput, forms.EmailInput,
                                   forms.Select, forms.NumberInput,
                                   forms.URLInput)):
                widget.attrs.setdefault("class", "form-control")
            elif isinstance(widget, forms.FileInput):
                widget.attrs.setdefault("class", "form-control")

    @staticmethod
    def _so_digitos(valor):
        import re
        return re.sub(r"\D", "", valor or "")

    def clean_cpf(self):
        return self._so_digitos(self.cleaned_data.get("cpf", ""))

    def clean_cep(self):
        return self._so_digitos(self.cleaned_data.get("cep", ""))

    def clean_telefone(self):
        return self._so_digitos(self.cleaned_data.get("telefone", ""))
