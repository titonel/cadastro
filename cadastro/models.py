from django.db import models
from django.core.validators import RegexValidator


class Especialidade(models.Model):
    nome = models.CharField(max_length=200, unique=True)
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Especialidade"
        verbose_name_plural = "Especialidades"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class TipoServico(models.TextChoices):
    CONSULTA = "consulta", "Consulta Ambulatorial"
    CIRURGIA_PEQUENO = "cirurgia_pequeno", "Cirurgia de Pequeno Porte"
    CIRURGIA_MEDIO = "cirurgia_medio", "Cirurgia de Médio Porte"
    EXAME = "exame", "Exame / Laudo"
    OUTRO = "outro", "Outro"


class Prestador(models.Model):
    # Dados da empresa
    nome_empresa = models.CharField("Razão Social", max_length=300)
    cnpj = models.CharField(
        "CNPJ",
        max_length=18,
        unique=True,
        validators=[RegexValidator(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$", "Formato: 00.000.000/0000-00")],
    )
    inscricao_municipal = models.CharField("Inscrição Municipal", max_length=50, blank=True)
    inscricao_estadual = models.CharField("Inscrição Estadual", max_length=50, blank=True, default="ISENTO")

    # Endereço
    logradouro = models.CharField("Logradouro", max_length=300)
    numero = models.CharField("Número", max_length=20)
    complemento = models.CharField("Complemento", max_length=100, blank=True)
    bairro = models.CharField("Bairro", max_length=150)
    cidade = models.CharField("Cidade", max_length=150)
    estado = models.CharField("Estado (UF)", max_length=2, default="SP")
    cep = models.CharField(
        "CEP",
        max_length=9,
        validators=[RegexValidator(r"^\d{5}-\d{3}$", "Formato: 00000-000")],
    )

    # Contato
    telefone = models.CharField("Telefone", max_length=20)
    email = models.EmailField("E-mail")

    # Representante Legal
    nome_representante = models.CharField("Nome do Representante Legal", max_length=200)
    cpf_representante = models.CharField(
        "CPF do Representante",
        max_length=14,
        validators=[RegexValidator(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$", "Formato: 000.000.000-00")],
    )
    crm_representante = models.CharField("CRM do Representante", max_length=30)

    # Testemunha
    nome_testemunha = models.CharField("Nome da Testemunha", max_length=200)
    telefone_testemunha = models.CharField("Telefone da Testemunha", max_length=20)
    email_testemunha = models.EmailField("E-mail da Testemunha")

    # Especialidades e serviços
    especialidades = models.ManyToManyField(
        Especialidade,
        verbose_name="Especialidades Médicas",
        related_name="prestadores",
    )

    # Vigência do contrato
    data_inicio_contrato = models.DateField("Início da Vigência")
    data_fim_contrato = models.DateField("Fim da Vigência")
    numero_processo = models.CharField("Número do Processo", max_length=50, blank=True)

    # Controle
    ativo = models.BooleanField("Ativo", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Prestador"
        verbose_name_plural = "Prestadores"
        ordering = ["nome_empresa"]

    def __str__(self):
        return self.nome_empresa

    @property
    def endereco_completo(self):
        partes = [f"{self.logradouro}, {self.numero}"]
        if self.complemento:
            partes.append(self.complemento)
        partes.append(f"{self.bairro} – {self.cidade}/{self.estado} – CEP: {self.cep}")
        return ", ".join(partes)


class ServicoContratado(models.Model):
    prestador = models.ForeignKey(Prestador, on_delete=models.CASCADE, related_name="servicos")
    especialidade = models.ForeignKey(
        Especialidade, on_delete=models.PROTECT, verbose_name="Especialidade", null=True, blank=True
    )
    tipo_servico = models.CharField("Tipo de Serviço", max_length=30, choices=TipoServico.choices)
    descricao = models.CharField("Descrição do Serviço", max_length=300)
    unidade_medida = models.CharField("Unidade de Medida", max_length=50, default="Consulta")
    quantidade_estimada_mes = models.PositiveIntegerField("Qtde. Estimada/Mês")
    valor_unitario = models.DecimalField("Valor Unitário (R$)", max_digits=10, decimal_places=2)
    prazo_entrega_laudo_dias = models.PositiveSmallIntegerField(
        "Prazo de Entrega do Laudo (dias úteis)", null=True, blank=True
    )
    remoto = models.BooleanField("Realizado Remotamente?", default=False)
    observacoes = models.TextField("Observações", blank=True)

    class Meta:
        verbose_name = "Serviço Contratado"
        verbose_name_plural = "Serviços Contratados"
        ordering = ["tipo_servico", "descricao"]

    def __str__(self):
        return f"{self.descricao} – {self.prestador.nome_empresa}"

    @property
    def valor_total_estimado_mes(self):
        return self.quantidade_estimada_mes * self.valor_unitario


class StatusImportacao(models.TextChoices):
    PENDENTE = "pendente", "Pendente de revisão"
    CONFIRMADO = "confirmado", "Confirmado e cadastrado"
    ERRO = "erro", "Erro na extração"
    IGNORADO = "ignorado", "Ignorado"


class ContratoUpload(models.Model):
    """Armazena um PDF de contrato enviado e os dados extraídos automaticamente."""
    arquivo = models.FileField("Arquivo PDF", upload_to="contratos_pdf/%Y/%m/")
    nome_arquivo = models.CharField(max_length=255, editable=False)
    enviado_em = models.DateTimeField(auto_now_add=True)

    # Dados extraídos
    razao_social_extraida = models.CharField("Razão Social (extraída)", max_length=300, blank=True)
    cnpj_extraido = models.CharField("CNPJ (extraído)", max_length=18, blank=True)
    objeto_extraido = models.TextField("Objeto do Contrato (extraído)", blank=True)
    servicos_extraidos = models.JSONField("Serviços (extraídos)", default=list, blank=True)
    especialidade_extraida = models.CharField("Especialidade (extraída)", max_length=200, blank=True)
    data_inicio_extraida = models.DateField("Data de Início (extraída)", null=True, blank=True)
    data_fim_extraida = models.DateField("Data Fim (extraída)", null=True, blank=True)
    meses_vigencia_extraidos = models.PositiveSmallIntegerField("Meses de Vigência", default=0)
    valor_mensal_extraido = models.DecimalField("Valor Mensal (extraído)", max_digits=12, decimal_places=2, default=0)
    valor_global_extraido = models.DecimalField("Valor Global (extraído)", max_digits=14, decimal_places=2, default=0)
    numero_processo_extraido = models.CharField("Nº do Processo (extraído)", max_length=50, blank=True)
    erro_extracao = models.TextField("Erro de Extração", blank=True)

    # Vínculo com prestador após confirmação
    prestador = models.ForeignKey(
        Prestador, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="contratos_importados",
        verbose_name="Prestador vinculado"
    )
    status = models.CharField(
        "Status", max_length=20,
        choices=StatusImportacao.choices,
        default=StatusImportacao.PENDENTE
    )

    class Meta:
        verbose_name = "Contrato Importado"
        verbose_name_plural = "Contratos Importados"
        ordering = ["-enviado_em"]

    def __str__(self):
        return f"{self.nome_arquivo} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if self.arquivo and not self.nome_arquivo:
            self.nome_arquivo = self.arquivo.name.split("/")[-1]
        super().save(*args, **kwargs)
