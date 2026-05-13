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
    logradouro = models.CharField("Logradouro", max_length=300, blank=True)
    numero = models.CharField("Número", max_length=20, blank=True)
    complemento = models.CharField("Complemento", max_length=100, blank=True)
    bairro = models.CharField("Bairro", max_length=150, blank=True)
    cidade = models.CharField("Cidade", max_length=150, blank=True)
    estado = models.CharField("Estado (UF)", max_length=2, default="SP", blank=True)
    cep = models.CharField(
        "CEP",
        max_length=9,
        blank=True,
        validators=[RegexValidator(r"^(\d{5}-\d{3})?$", "Formato: 00000-000")],
    )

    # Contato
    telefone = models.CharField("Telefone", max_length=20, blank=True)
    email = models.EmailField("E-mail", blank=True)

    # Representante Legal
    nome_representante = models.CharField("Nome do Representante Legal", max_length=200, blank=True)
    cpf_representante = models.CharField(
        "CPF do Representante",
        max_length=14,
        blank=True,
        validators=[RegexValidator(r"^(\d{3}\.\d{3}\.\d{3}-\d{2})?$", "Formato: 000.000.000-00")],
    )
    crm_representante = models.CharField("CRM do Representante", max_length=30, blank=True)

    # Testemunha
    nome_testemunha = models.CharField("Nome da Testemunha", max_length=200, blank=True)
    telefone_testemunha = models.CharField("Telefone da Testemunha", max_length=20, blank=True)
    email_testemunha = models.EmailField("E-mail da Testemunha", blank=True)

    # Especialidades e serviços
    especialidades = models.ManyToManyField(
        Especialidade,
        verbose_name="Especialidades Médicas",
        related_name="prestadores",
        blank=True,
    )

    # Vigência do contrato
    data_inicio_contrato = models.DateField("Início da Vigência", null=True, blank=True)
    data_fim_contrato = models.DateField("Fim da Vigência", null=True, blank=True)
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
        partes = []
        if self.logradouro:
            partes.append(f"{self.logradouro}, {self.numero}" if self.numero else self.logradouro)
        if self.complemento:
            partes.append(self.complemento)
        loc = " – ".join(filter(None, [self.bairro, f"{self.cidade}/{self.estado}" if self.cidade else ""]))
        if loc:
            partes.append(f"{loc} – CEP: {self.cep}" if self.cep else loc)
        return ", ".join(partes)


class ServicoContratado(models.Model):
    prestador = models.ForeignKey(Prestador, on_delete=models.CASCADE, related_name="servicos")
    especialidade = models.ForeignKey(
        Especialidade, on_delete=models.PROTECT, verbose_name="Especialidade", null=True, blank=True
    )
    tipo_servico = models.CharField("Tipo de Serviço", max_length=30, choices=TipoServico.choices, blank=True)
    descricao = models.CharField("Descrição do Serviço", max_length=300, blank=True)
    unidade_medida = models.CharField("Unidade de Medida", max_length=50, default="Consulta", blank=True)
    quantidade_estimada_mes = models.PositiveIntegerField("Qtde. Estimada/Mês", default=0)
    valor_unitario = models.DecimalField("Valor Unitário (R$)", max_digits=10, decimal_places=2, default=0)
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


# ─────────────────────────────────────────────────────────────────────────────
# Módulo: Produção SIRESP
# ─────────────────────────────────────────────────────────────────────────────

class TipoRelatorioProducao(models.TextChoices):
    CONSULTA = "consulta", "Consultas"
    CIRURGIA_EXAME = "cirurgia_exame", "Cirurgias / Exames"


class UploadProducao(models.Model):
    """Registro de cada arquivo XLS do SIRESP enviado para importação."""
    arquivo = models.FileField("Arquivo XLS", upload_to="producao_xls/%Y/%m/")
    nome_arquivo = models.CharField(max_length=255, editable=False)
    tipo = models.CharField(
        "Tipo de Relatório",
        max_length=20,
        choices=TipoRelatorioProducao.choices,
        default=TipoRelatorioProducao.CONSULTA,
    )
    data_inicio_periodo = models.DateField("Início do Período", null=True, blank=True)
    data_fim_periodo = models.DateField("Fim do Período", null=True, blank=True)
    enviado_em = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        "Status",
        max_length=20,
        choices=StatusImportacao.choices,
        default=StatusImportacao.PENDENTE,
    )
    erro_processamento = models.TextField("Erro de Processamento", blank=True)
    total_agendas = models.PositiveIntegerField("Total de Agendas", default=0)
    total_medicos = models.PositiveIntegerField("Total de Registros de Médicos", default=0)

    class Meta:
        verbose_name = "Upload de Produção"
        verbose_name_plural = "Uploads de Produção"
        ordering = ["-enviado_em"]

    def __str__(self):
        return f"{self.nome_arquivo} ({self.get_tipo_display()}) — {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if self.arquivo and not self.nome_arquivo:
            import os
            self.nome_arquivo = os.path.basename(self.arquivo.name)
        super().save(*args, **kwargs)

    @property
    def periodo_display(self):
        if self.data_inicio_periodo and self.data_fim_periodo:
            return f"{self.data_inicio_periodo.strftime('%d/%m/%Y')} a {self.data_fim_periodo.strftime('%d/%m/%Y')}"
        return "—"


# Mapeamento das colunas do SIRESP (índice 0-based a partir da coluna A)
COLUNAS_SIRESP = [
    "especialidade_medica",      # A  (0)
    "vagas_ofertadas",           # B  (1)
    "agend_totais",              # C  (2)
    "agend_totais_pct",          # D  (3)
    "agend_bolsao",              # E  (4)
    "agend_bolsao_pct",          # F  (5)
    "nao_distribuidas",          # G  (6)
    "nao_distribuidas_pct",      # H  (7)
    "cota",                      # I  (8)
    "cota_pct",                  # J  (9)
    "extra",                     # K  (10)
    "extra_pct",                 # L  (11)
    "total_geral",               # M  (12)
    "presencial",                # N  (13)
    "presencial_pct",            # O  (14)
    "teleconsulta",              # P  (15)
    "teleconsulta_pct",          # Q  (16)
    "agend_totais_2",            # R  (17)
    "agend_totais_2_pct",        # S  (18)
    "recepcao_ausente",          # T  (19)
    "recepcao_ausente_pct",      # U  (20)
    "recepcao_dispensado",       # V  (21)
    "recepcao_dispensado_pct",   # W  (22)
    "recepcao_desistente",       # X  (23)
    "recepcao_desistente_pct",   # Y  (24)
    "recepcao_nao_informado",    # Z  (25)
    "recepcao_nao_informado_pct",# AA (26)
    "alta",                      # AB (27)
    "alta_pct",                  # AC (28)
]


# Mapeamento das colunas do SIRESP — relatório de Cirurgias/Exames (A–Y, 25 colunas)
# Coluna N "Atendidos" é mapeada em `presencial`; teleconsulta e agend_totais_2 ficam em 0.
COLUNAS_SIRESP_EXAMES = [
    "especialidade_medica",       # A  (0)  Procedimento
    "vagas_ofertadas",            # B  (1)
    "agend_totais",               # C  (2)
    "agend_totais_pct",           # D  (3)
    "agend_bolsao",               # E  (4)
    "agend_bolsao_pct",           # F  (5)
    "nao_distribuidas",           # G  (6)
    "nao_distribuidas_pct",       # H  (7)
    "cota",                       # I  (8)
    "cota_pct",                   # J  (9)
    "extra",                      # K  (10)
    "extra_pct",                  # L  (11)
    "total_geral",                # M  (12)
    "presencial",                 # N  (13)  Atendidos
    "presencial_pct",             # O  (14)  Atendidos %
    "recepcao_ausente",           # P  (15)
    "recepcao_ausente_pct",       # Q  (16)
    "recepcao_dispensado",        # R  (17)
    "recepcao_dispensado_pct",    # S  (18)
    "recepcao_desistente",        # T  (19)
    "recepcao_desistente_pct",    # U  (20)
    "recepcao_nao_informado",     # V  (21)
    "recepcao_nao_informado_pct", # W  (22)
    "alta",                       # X  (23)
    "alta_pct",                   # Y  (24)
]


class ProducaoAgenda(models.Model):
    """Produção consolidada de uma agenda (especialidade) em um período."""
    upload = models.ForeignKey(
        UploadProducao, on_delete=models.CASCADE, related_name="agendas"
    )
    nome_agenda = models.CharField("Nome da Agenda", max_length=200)

    vagas_ofertadas = models.IntegerField(default=0)
    agend_totais = models.IntegerField(default=0)
    agend_totais_pct = models.FloatField(default=0)
    agend_bolsao = models.IntegerField(default=0)
    agend_bolsao_pct = models.FloatField(default=0)
    nao_distribuidas = models.IntegerField(default=0)
    nao_distribuidas_pct = models.FloatField(default=0)
    cota = models.IntegerField(default=0)
    cota_pct = models.FloatField(default=0)
    extra = models.IntegerField(default=0)
    extra_pct = models.FloatField(default=0)
    total_geral = models.IntegerField(default=0)
    presencial = models.IntegerField(default=0)
    presencial_pct = models.FloatField(default=0)
    teleconsulta = models.IntegerField(default=0)
    teleconsulta_pct = models.FloatField(default=0)
    agend_totais_2 = models.IntegerField(default=0)
    agend_totais_2_pct = models.FloatField(default=0)
    recepcao_ausente = models.IntegerField(default=0)
    recepcao_ausente_pct = models.FloatField(default=0)
    recepcao_dispensado = models.IntegerField(default=0)
    recepcao_dispensado_pct = models.FloatField(default=0)
    recepcao_desistente = models.IntegerField(default=0)
    recepcao_desistente_pct = models.FloatField(default=0)
    recepcao_nao_informado = models.IntegerField(default=0)
    recepcao_nao_informado_pct = models.FloatField(default=0)
    alta = models.IntegerField(default=0)
    alta_pct = models.FloatField(default=0)

    class Meta:
        verbose_name = "Produção por Agenda"
        verbose_name_plural = "Produções por Agenda"
        ordering = ["nome_agenda"]
        unique_together = [("upload", "nome_agenda")]

    def __str__(self):
        return f"{self.nome_agenda} — {self.upload}"


class ProducaoMedico(models.Model):
    """Produção individual de um médico dentro de uma agenda em um período."""
    agenda = models.ForeignKey(
        ProducaoAgenda, on_delete=models.CASCADE, related_name="medicos"
    )
    nome_medico = models.CharField("Nome do Médico", max_length=200)

    vagas_ofertadas = models.IntegerField(default=0)
    agend_totais = models.IntegerField(default=0)
    agend_totais_pct = models.FloatField(default=0)
    agend_bolsao = models.IntegerField(default=0)
    agend_bolsao_pct = models.FloatField(default=0)
    nao_distribuidas = models.IntegerField(default=0)
    nao_distribuidas_pct = models.FloatField(default=0)
    cota = models.IntegerField(default=0)
    cota_pct = models.FloatField(default=0)
    extra = models.IntegerField(default=0)
    extra_pct = models.FloatField(default=0)
    total_geral = models.IntegerField(default=0)
    presencial = models.IntegerField(default=0)
    presencial_pct = models.FloatField(default=0)
    teleconsulta = models.IntegerField(default=0)
    teleconsulta_pct = models.FloatField(default=0)
    agend_totais_2 = models.IntegerField(default=0)
    agend_totais_2_pct = models.FloatField(default=0)
    recepcao_ausente = models.IntegerField(default=0)
    recepcao_ausente_pct = models.FloatField(default=0)
    recepcao_dispensado = models.IntegerField(default=0)
    recepcao_dispensado_pct = models.FloatField(default=0)
    recepcao_desistente = models.IntegerField(default=0)
    recepcao_desistente_pct = models.FloatField(default=0)
    recepcao_nao_informado = models.IntegerField(default=0)
    recepcao_nao_informado_pct = models.FloatField(default=0)
    alta = models.IntegerField(default=0)
    alta_pct = models.FloatField(default=0)

    class Meta:
        verbose_name = "Produção por Médico"
        verbose_name_plural = "Produções por Médico"
        ordering = ["nome_medico"]

    def __str__(self):
        return f"{self.nome_medico} — {self.agenda.nome_agenda}"


class Medico(models.Model):
    """Cadastro individual de médico credenciado no AME Caraguatatuba."""

    # ── Dados pessoais ──────────────────────────────────────────────────────
    nome_completo = models.CharField("Nome Completo", max_length=300)
    cpf = models.CharField(
        "CPF",
        max_length=14,
        unique=True,
        blank=True,
        validators=[RegexValidator(r"^(\d{3}\.\d{3}\.\d{3}-\d{2})?$", "Formato: 000.000.000-00")],
    )
    crm = models.CharField("CRM", max_length=20, blank=True)
    rqe = models.CharField("RQE", max_length=30, blank=True,
                            help_text="Registro de Qualificação de Especialista (opcional)")
    foto = models.ImageField(
        "Foto", upload_to="medicos/fotos/%Y/",
        null=True, blank=True,
        help_text="Foto de perfil do médico (JPG ou PNG)"
    )

    # ── Contato ─────────────────────────────────────────────────────────────
    telefone = models.CharField("Telefone / WhatsApp", max_length=20, blank=True)
    email    = models.EmailField("E-mail", blank=True)

    # ── Endereço ─────────────────────────────────────────────────────────────
    cep         = models.CharField("CEP", max_length=9, blank=True,
                                   validators=[RegexValidator(r"^(\d{5}-\d{3})?$", "Formato: 00000-000")])
    logradouro  = models.CharField("Logradouro", max_length=300, blank=True)
    numero      = models.CharField("Número",     max_length=20,  blank=True)
    complemento = models.CharField("Complemento",max_length=100, blank=True)
    bairro      = models.CharField("Bairro",     max_length=150, blank=True)
    cidade      = models.CharField("Cidade",     max_length=150, blank=True)
    estado      = models.CharField("Estado (UF)",max_length=2,   blank=True, default="SP")

    # ── Vínculo profissional ─────────────────────────────────────────────────
    especialidades = models.ManyToManyField(
        Especialidade,
        verbose_name="Especialidades no AME",
        related_name="medicos",
        blank=True,
    )
    prestador = models.ForeignKey(
        Prestador,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="medicos",
        verbose_name="Empresa Prestadora",
    )

    # ── Controle ─────────────────────────────────────────────────────────────
    ativo      = models.BooleanField("Ativo", default=True)
    criado_em  = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Médico"
        verbose_name_plural = "Médicos"
        ordering = ["nome_completo"]

    def __str__(self):
        return f"{self.nome_completo} — CRM {self.crm}" if self.crm else self.nome_completo

    @property
    def endereco_completo(self):
        partes = []
        if self.logradouro:
            partes.append(f"{self.logradouro}, {self.numero}" if self.numero else self.logradouro)
        if self.complemento:
            partes.append(self.complemento)
        loc = " – ".join(filter(None, [
            self.bairro,
            f"{self.cidade}/{self.estado}" if self.cidade else "",
        ]))
        if loc:
            partes.append(f"{loc} – CEP: {self.cep}" if self.cep else loc)
        return ", ".join(partes)


class AgendaMapeamento(models.Model):
    """
    Tabela de correspondência entre um ServicoContratado e os nomes
    de agenda do SIRESP que representam aquele serviço.

    Exemplo:
      ServicoContratado(descricao="Cardiologia") →
        AgendaMapeamento(nome_agenda="Cardiologia")
        AgendaMapeamento(nome_agenda="Cardiologia - Hipertensão")
        AgendaMapeamento(nome_agenda="Cardiologia - Saude do Homem")
    """
    servico = models.ForeignKey(
        ServicoContratado,
        on_delete=models.CASCADE,
        related_name="mapeamentos",
        verbose_name="Serviço Contratado",
    )
    nome_agenda = models.CharField(
        "Nome da Agenda no SIRESP",
        max_length=200,
        help_text="Nome exato como aparece no relatório do SIRESP (P05 Produção x Profissional)",
    )

    class Meta:
        verbose_name = "Mapeamento de Agenda"
        verbose_name_plural = "Mapeamentos de Agenda"
        ordering = ["servico", "nome_agenda"]
        unique_together = [("servico", "nome_agenda")]

    def __str__(self):
        return f"{self.servico.descricao} → {self.nome_agenda}"
