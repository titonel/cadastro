# Generated manually – cobre todos os models iniciais incluindo ContratoUpload
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Especialidade",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=200, unique=True)),
                ("ativa", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Especialidade",
                "verbose_name_plural": "Especialidades",
                "ordering": ["nome"],
            },
        ),
        migrations.CreateModel(
            name="Prestador",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome_empresa", models.CharField(max_length=300, verbose_name="Razão Social")),
                ("cnpj", models.CharField(
                    max_length=18, unique=True, verbose_name="CNPJ",
                    validators=[django.core.validators.RegexValidator(
                        r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$", "Formato: 00.000.000/0000-00"
                    )],
                )),
                ("inscricao_municipal", models.CharField(blank=True, max_length=50, verbose_name="Inscrição Municipal")),
                ("inscricao_estadual", models.CharField(blank=True, default="ISENTO", max_length=50, verbose_name="Inscrição Estadual")),
                ("logradouro", models.CharField(max_length=300, verbose_name="Logradouro")),
                ("numero", models.CharField(max_length=20, verbose_name="Número")),
                ("complemento", models.CharField(blank=True, max_length=100, verbose_name="Complemento")),
                ("bairro", models.CharField(max_length=150, verbose_name="Bairro")),
                ("cidade", models.CharField(max_length=150, verbose_name="Cidade")),
                ("estado", models.CharField(default="SP", max_length=2, verbose_name="Estado (UF)")),
                ("cep", models.CharField(
                    max_length=9, verbose_name="CEP",
                    validators=[django.core.validators.RegexValidator(
                        r"^\d{5}-\d{3}$", "Formato: 00000-000"
                    )],
                )),
                ("telefone", models.CharField(max_length=20, verbose_name="Telefone")),
                ("email", models.EmailField(max_length=254, verbose_name="E-mail")),
                ("nome_representante", models.CharField(max_length=200, verbose_name="Nome do Representante Legal")),
                ("cpf_representante", models.CharField(
                    max_length=14, verbose_name="CPF do Representante",
                    validators=[django.core.validators.RegexValidator(
                        r"^\d{3}\.\d{3}\.\d{3}-\d{2}$", "Formato: 000.000.000-00"
                    )],
                )),
                ("crm_representante", models.CharField(max_length=30, verbose_name="CRM do Representante")),
                ("nome_testemunha", models.CharField(max_length=200, verbose_name="Nome da Testemunha")),
                ("telefone_testemunha", models.CharField(max_length=20, verbose_name="Telefone da Testemunha")),
                ("email_testemunha", models.EmailField(max_length=254, verbose_name="E-mail da Testemunha")),
                ("especialidades", models.ManyToManyField(
                    related_name="prestadores", to="cadastro.especialidade",
                    verbose_name="Especialidades Médicas",
                )),
                ("data_inicio_contrato", models.DateField(verbose_name="Início da Vigência")),
                ("data_fim_contrato", models.DateField(verbose_name="Fim da Vigência")),
                ("numero_processo", models.CharField(blank=True, max_length=50, verbose_name="Número do Processo")),
                ("ativo", models.BooleanField(default=True, verbose_name="Ativo")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Prestador",
                "verbose_name_plural": "Prestadores",
                "ordering": ["nome_empresa"],
            },
        ),
        migrations.CreateModel(
            name="ServicoContratado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("prestador", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="servicos", to="cadastro.prestador",
                )),
                ("especialidade", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    to="cadastro.especialidade", verbose_name="Especialidade",
                )),
                ("tipo_servico", models.CharField(
                    choices=[
                        ("consulta", "Consulta Ambulatorial"),
                        ("cirurgia_pequeno", "Cirurgia de Pequeno Porte"),
                        ("cirurgia_medio", "Cirurgia de Médio Porte"),
                        ("exame", "Exame / Laudo"),
                        ("outro", "Outro"),
                    ],
                    max_length=30, verbose_name="Tipo de Serviço",
                )),
                ("descricao", models.CharField(max_length=300, verbose_name="Descrição do Serviço")),
                ("unidade_medida", models.CharField(default="Consulta", max_length=50, verbose_name="Unidade de Medida")),
                ("quantidade_estimada_mes", models.PositiveIntegerField(verbose_name="Qtde. Estimada/Mês")),
                ("valor_unitario", models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Valor Unitário (R$)")),
                ("prazo_entrega_laudo_dias", models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    verbose_name="Prazo de Entrega do Laudo (dias úteis)",
                )),
                ("remoto", models.BooleanField(default=False, verbose_name="Realizado Remotamente?")),
                ("observacoes", models.TextField(blank=True, verbose_name="Observações")),
            ],
            options={
                "verbose_name": "Serviço Contratado",
                "verbose_name_plural": "Serviços Contratados",
                "ordering": ["tipo_servico", "descricao"],
            },
        ),
        migrations.CreateModel(
            name="ContratoUpload",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("arquivo", models.FileField(upload_to="contratos_pdf/%Y/%m/", verbose_name="Arquivo PDF")),
                ("nome_arquivo", models.CharField(editable=False, max_length=255)),
                ("enviado_em", models.DateTimeField(auto_now_add=True)),
                ("razao_social_extraida", models.CharField(blank=True, max_length=300, verbose_name="Razão Social (extraída)")),
                ("cnpj_extraido", models.CharField(blank=True, max_length=18, verbose_name="CNPJ (extraído)")),
                ("objeto_extraido", models.TextField(blank=True, verbose_name="Objeto do Contrato (extraído)")),
                ("servicos_extraidos", models.JSONField(blank=True, default=list, verbose_name="Serviços (extraídos)")),
                ("especialidade_extraida", models.CharField(blank=True, max_length=200, verbose_name="Especialidade (extraída)")),
                ("data_inicio_extraida", models.DateField(blank=True, null=True, verbose_name="Data de Início (extraída)")),
                ("data_fim_extraida", models.DateField(blank=True, null=True, verbose_name="Data Fim (extraída)")),
                ("meses_vigencia_extraidos", models.PositiveSmallIntegerField(default=0, verbose_name="Meses de Vigência")),
                ("valor_mensal_extraido", models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name="Valor Mensal (extraído)")),
                ("valor_global_extraido", models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name="Valor Global (extraído)")),
                ("numero_processo_extraido", models.CharField(blank=True, max_length=50, verbose_name="Nº do Processo (extraído)")),
                ("erro_extracao", models.TextField(blank=True, verbose_name="Erro de Extração")),
                ("prestador", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="contratos_importados",
                    to="cadastro.prestador", verbose_name="Prestador vinculado",
                )),
                ("status", models.CharField(
                    choices=[
                        ("pendente", "Pendente de revisão"),
                        ("confirmado", "Confirmado e cadastrado"),
                        ("erro", "Erro na extração"),
                        ("ignorado", "Ignorado"),
                    ],
                    default="pendente", max_length=20, verbose_name="Status",
                )),
            ],
            options={
                "verbose_name": "Contrato Importado",
                "verbose_name_plural": "Contratos Importados",
                "ordering": ["-enviado_em"],
            },
        ),
    ]
