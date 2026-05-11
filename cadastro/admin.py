from django.contrib import admin
from .models import Prestador, ServicoContratado, Especialidade


@admin.register(Especialidade)
class EspecialidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativa")
    list_filter = ("ativa",)
    search_fields = ("nome",)


class ServicoInline(admin.TabularInline):
    model = ServicoContratado
    extra = 0
    fields = ("tipo_servico", "descricao", "unidade_medida", "quantidade_estimada_mes", "valor_unitario", "prazo_entrega_laudo_dias", "remoto")


@admin.register(Prestador)
class PrestadorAdmin(admin.ModelAdmin):
    list_display = ("nome_empresa", "cnpj", "nome_representante", "crm_representante", "data_inicio_contrato", "data_fim_contrato", "ativo")
    list_filter = ("ativo", "especialidades", "estado")
    search_fields = ("nome_empresa", "cnpj", "nome_representante", "crm_representante")
    filter_horizontal = ("especialidades",)
    inlines = [ServicoInline]
    fieldsets = (
        ("Dados da Empresa", {
            "fields": ("nome_empresa", "cnpj", "inscricao_municipal", "inscricao_estadual")
        }),
        ("Endereço", {
            "fields": ("logradouro", "numero", "complemento", "bairro", "cidade", "estado", "cep")
        }),
        ("Contato", {
            "fields": ("telefone", "email")
        }),
        ("Representante Legal", {
            "fields": ("nome_representante", "cpf_representante", "crm_representante")
        }),
        ("Testemunha", {
            "fields": ("nome_testemunha", "telefone_testemunha", "email_testemunha")
        }),
        ("Especialidades e Contrato", {
            "fields": ("especialidades", "data_inicio_contrato", "data_fim_contrato", "numero_processo", "ativo")
        }),
    )


@admin.register(ServicoContratado)
class ServicoAdmin(admin.ModelAdmin):
    list_display = ("descricao", "prestador", "tipo_servico", "quantidade_estimada_mes", "valor_unitario")
    list_filter = ("tipo_servico", "remoto")
    search_fields = ("descricao", "prestador__nome_empresa")
    autocomplete_fields = ("prestador",)
