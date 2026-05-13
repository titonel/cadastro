"""
Producao SIRESP — parser de arquivo XLS/XLSX exportado do portal SIRESP.

Estrutura esperada:
  B2  : "Período:DD-MM-AAAAaDD-MM-AAAA"
  Linha 9  : cabeçalhos (ignorados — usamos COLUNAS_SIRESP)
  Linha 10+: dados

Regras de identificação na coluna A:
  - Nome da agenda  → Title Case (ex: "Oftalmologia - Catarata")
  - Nome do médico  → UPPER CASE  (ex: "JOAO DA SILVA")
  - "Total Geral"   → linha de rodapé — encerra o processamento
  - Demais linhas de total/subtotal/rodapé → ignoradas

Formatos suportados:
  .xlsx / .xlsm  → openpyxl
  .xls  (legado binário)  → xlrd  (pip install "xlrd==1.2.0")
  .xls  (HTML disfarçado) → pandas.read_html()
    O SIRESP exporta arquivos .xls que são, na verdade, documentos HTML
    completos (ISO-8859-1). Esses arquivos NÃO possuem a assinatura binária
    OLE2/BIFF e são detectados pelo prefixo "<" (tag HTML) no conteúdo.

O formato é detectado automaticamente pelo cabeçalho do arquivo,
não pela extensão.

NOTA: upload.arquivo.read() após upload.save() retorna bytes vazios porque
o Django já consumiu o stream ao gravar no disco. Por isso usamos
upload.arquivo.open("rb") para reler do storage após o save.
"""

import io
import re
from datetime import date, datetime
from typing import Optional

import openpyxl
import pandas as pd
import xlrd

from .models import (
    UploadProducao, ProducaoAgenda, ProducaoMedico,
    StatusImportacao, COLUNAS_SIRESP,
)

# Assinatura binária do formato XLS legado (BIFF/OLE2 Compound Document)
_XLS_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# O SIRESP exporta arquivos .xls que são HTML puro (ISO-8859-1).
# Detectamos pelo byte inicial "<" (0x3C), característico de tags HTML.
_HTML_MAGIC = b"<"

# Lista canônica de agendas (para validação cruzada futura)
AGENDAS_CONHECIDAS = {
    "Anestesiologia - Avaliação Pré-cirúrgica",
    "Cardiologia",
    "Cardiologia - Hipertensão",
    "Cardiologia - Saude do Homem",
    "Cirurgia Geral",
    "Cirurgia Geral - Pós Operatório",
    "Cirurgia Pediátrica",
    "Cirurgia Pediátrica - Pós Operatório",
    "Cirurgia Plástica",
    "Cirurgia Plástica - Pós Operatório",
    "Cirurgia Plástica - Tumor Pele e Outros",
    "Cirurgia Vascular",
    "Cirurgia Vascular - Pós Operatório",
    "Coloproctologia",
    "Coloproctologia - Pós Operatório",
    "Dermatologia",
    "Dermatologia - Pós Cirúrgica",
    "Endocrinologia",
    "Enfermagem",
    "Enfermagem - Biópsia de Próstata",
    "Enfermagem - Cardiologia",
    "Enfermagem - Cistoscopia",
    "Enfermagem - Hipertensão",
    "Enfermagem - Microcefalia - Linha de Cuidado",
    "Enfermagem - Multiorientações",
    "Enfermagem - Orientação Cirúrgica",
    "Enfermagem - Saude do Homem",
    "Farmacêutico - Orientação de Protocolo",
    "Farmácia",
    "Gastroclínica",
    "Gastroclínica - Triagem Colonoscopia",
    "Gastroclínica - Triagem Endoscopia",
    "Mastologia",
    "Mastologia - Pós-operatório",
    "Neurologia",
    "Neurologia - Sífilis Congênita",
    "Neurologia Pediátrica",
    "Nutrição",
    "Oftalmologia",
    "Oftalmologia - Avaliação Cirúrgica",
    "Oftalmologia - Avaliação Pós-cirúrgica",
    "Oftalmologia - Catarata",
    "Oftalmologia - Microcefalia - Linha de Cuidado",
    "Oftalmologia - Pterígio",
    "Oftalmologia - Reflexo Vermelho",
    "Oftalmologia - Retina",
    "Oftalmologia - Sífilis Congênita",
    "Ortopedia",
    "Ortopedia - Pós-operatório",
    "Otorrinolaringologia",
    "Otorrinolaringologia - Nasofibroscopia",
    "Otorrinolaringologia - Sífilis Congênita",
    "Pneumologia",
    "Pneumologia Pediátrica",
    "Serviço Social",
    "Urologia",
    "Urologia - Avaliação Pós-cirúrgica",
    "Urologia - Saude do Homem",
    "Urologia - Vasectomia",
}

# Padrão do campo de período na célula B2
_PERIODO_RE = re.compile(
    r"Per[ií]odo[:\s]*"
    r"(\d{2}-\d{2}-\d{4})"
    r"[aA]"
    r"(\d{2}-\d{2}-\d{4})",
    re.IGNORECASE,
)


def _parse_date(s: str) -> Optional[date]:
    """Converte 'DD-MM-AAAA' em date."""
    try:
        return datetime.strptime(s.strip(), "%d-%m-%Y").date()
    except (ValueError, AttributeError):
        return None


def _safe_int(value) -> int:
    try:
        return int(float(str(value).replace(",", ".").strip()))
    except (ValueError, TypeError):
        return 0


def _safe_float(value) -> float:
    try:
        return float(str(value).replace(",", ".").replace("%", "").strip())
    except (ValueError, TypeError):
        return 0.0


def _eh_total_geral(texto: str) -> bool:
    """Retorna True se a linha é o rodapé 'Total Geral' — encerra o processamento."""
    return texto.strip().lower() == "total geral"


def _eh_agenda(texto: str) -> bool:
    if not texto or len(texto) < 3:
        return False
    texto = texto.strip()
    palavras_descarte = (
        "total", "subtotal", "grand total", "período",
        "especialidade", "vagas", "agendamentos",
    )
    lower = texto.lower()
    for p in palavras_descarte:
        if lower.startswith(p):
            return False
    letras = [c for c in texto if c.isalpha()]
    if not letras:
        return False
    if all(c.isupper() for c in letras):
        return False  # é médico
    return letras[0].isupper()


def _eh_medico(texto: str) -> bool:
    if not texto or len(texto) < 3:
        return False
    letras = [c for c in texto.strip() if c.isalpha()]
    if not letras:
        return False
    return all(c.isupper() for c in letras)


def _preencher_campos_numericos(obj, dados: dict):
    campos_int = [
        "vagas_ofertadas", "agend_totais", "agend_bolsao", "nao_distribuidas",
        "cota", "extra", "total_geral", "presencial", "teleconsulta",
        "agend_totais_2", "recepcao_ausente", "recepcao_dispensado",
        "recepcao_desistente", "recepcao_nao_informado", "alta",
    ]
    campos_float = [
        "agend_totais_pct", "agend_bolsao_pct", "nao_distribuidas_pct",
        "cota_pct", "extra_pct", "presencial_pct", "teleconsulta_pct",
        "agend_totais_2_pct", "recepcao_ausente_pct", "recepcao_dispensado_pct",
        "recepcao_desistente_pct", "recepcao_nao_informado_pct", "alta_pct",
    ]
    for campo in campos_int:
        if campo in dados:
            setattr(obj, campo, _safe_int(dados[campo]))
    for campo in campos_float:
        if campo in dados:
            setattr(obj, campo, _safe_float(dados[campo]))


# ---------------------------------------------------------------------------
# Adaptadores de formato — interface uniforme para XLS e XLSX
# ---------------------------------------------------------------------------

class _SheetXlsx:
    """Wrapper sobre openpyxl worksheet."""

    def __init__(self, ws):
        self._ws = ws
        self.n_colunas = len(COLUNAS_SIRESP)

    def cell_b2(self) -> str:
        val = self._ws["B2"].value
        return str(val).strip() if val is not None else ""

    def iter_linhas(self):
        for row in self._ws.iter_rows(min_row=10, max_col=self.n_colunas):
            dados = {}
            for col_idx, cell in enumerate(row[:self.n_colunas]):
                nome = COLUNAS_SIRESP[col_idx]
                val = cell.value
                if val is None:
                    val = ""
                elif isinstance(val, str):
                    val = val.strip()
                dados[nome] = val
            yield dados


class _SheetXls:
    """Wrapper sobre xlrd sheet."""

    def __init__(self, sheet):
        self._sheet = sheet
        self.n_colunas = len(COLUNAS_SIRESP)

    def cell_b2(self) -> str:
        return str(self._sheet.cell_value(1, 1)).strip()

    def iter_linhas(self):
        sheet = self._sheet
        n = min(self.n_colunas, sheet.ncols)
        for row_idx in range(9, sheet.nrows):
            dados = {}
            for col_idx in range(n):
                nome = COLUNAS_SIRESP[col_idx]
                raw = sheet.cell_value(row_idx, col_idx)
                if isinstance(raw, str):
                    raw = raw.strip()
                dados[nome] = raw
            yield dados


class _SheetHtml:
    """
    Wrapper para arquivos .xls exportados pelo SIRESP que são, na verdade,
    documentos HTML (ISO-8859-1) disfarçados de XLS.

    O pandas.read_html() localiza a maior tabela do documento e itera
    suas linhas a partir da linha 10 (índice 9 após os 4 cabeçalhos
    hierárquicos do SIRESP).

    O campo de período é extraído a partir do texto de metadados presente
    nas tabelas menores que precedem a tabela principal.
    """

    # O SIRESP usa 4 linhas de cabeçalho hierárquico (colspan/rowspan)
    # antes dos dados propriamente ditos.
    _N_CABECALHOS = 4

    def __init__(self, conteudo: bytes):
        html = conteudo.decode("iso-8859-1", errors="replace")
        # thousands='.' e decimal=',' tratam a formatação numérica brasileira:
        # "1.234" → 1234  e  "95,51" → 95.51
        self._tables = pd.read_html(
            io.StringIO(html),
            header=None,
            thousands=".",
            decimal=",",
        )
        self._tabela_principal = self._identificar_tabela_principal()
        self.n_colunas = len(COLUNAS_SIRESP)

    def _identificar_tabela_principal(self) -> pd.DataFrame:
        """Retorna o DataFrame com mais linhas — é sempre a tabela de dados."""
        if not self._tables:
            raise ValueError("Nenhuma tabela HTML encontrada no arquivo.")
        return max(self._tables, key=len)

    def cell_b2(self) -> str:
        """
        Extrai o texto de período varrendendo todas as tabelas de metadados.
        O SIRESP grava o período num campo como:
          "Unidade Executante:AME X  Período:01-04-2026a30-04-2026  ..."
        """
        for table in self._tables:
            for valor in table.values.flatten():
                if isinstance(valor, str) and "Período:" in valor:
                    return valor
        return ""

    def iter_linhas(self):
        """
        Itera as linhas de dados (a partir da linha 10, ou seja, após os
        4 cabeçalhos hierárquicos do SIRESP) retornando dicionários com
        os nomes de COLUNAS_SIRESP como chaves.
        """
        df = self._tabela_principal.iloc[self._N_CABECALHOS:].reset_index(drop=True)
        n = min(self.n_colunas, df.shape[1])
        for _, row in df.iterrows():
            dados = {}
            for col_idx in range(n):
                nome = COLUNAS_SIRESP[col_idx]
                val = row.iloc[col_idx]
                if pd.isna(val):
                    val = ""
                elif not isinstance(val, str):
                    val = str(val)
                dados[nome] = val
            yield dados


def _abrir_sheet(conteudo: bytes):
    """
    Detecta o formato pelo cabeçalho do arquivo e retorna o wrapper correto.

      HTML (SIRESP): primeiro byte == "<"           → _SheetHtml
      XLS   (BIFF) : primeiros 8 bytes == _XLS_MAGIC → _SheetXls
      Qualquer outro caso (ZIP/OOXML)               → _SheetXlsx
    """
    if conteudo[:1] == _HTML_MAGIC:
        return _SheetHtml(conteudo)
    elif conteudo[:8] == _XLS_MAGIC:
        wb = xlrd.open_workbook(file_contents=conteudo)
        return _SheetXls(wb.sheets()[0])
    else:
        wb = openpyxl.load_workbook(filename=io.BytesIO(conteudo), data_only=True)
        return _SheetXlsx(wb.active)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def processar_upload(upload_id: int) -> None:
    """
    Lê o arquivo (XLS ou XLSX) associado ao UploadProducao e persiste
    ProducaoAgenda + ProducaoMedico no banco.

    IMPORTANTE: usa upload.arquivo.open("rb") para reler o arquivo do
    storage após upload.save(), evitando o problema de stream já consumido.
    """
    upload = UploadProducao.objects.get(pk=upload_id)

    # Reabre o arquivo do disco/storage (o stream original já foi consumido
    # pelo Django ao fazer upload.save() na view)
    with upload.arquivo.open("rb") as f:
        conteudo = f.read()

    sheet = _abrir_sheet(conteudo)

    # — Extrai período da célula B2 —
    match = _PERIODO_RE.search(sheet.cell_b2())
    if match:
        upload.data_inicio_periodo = _parse_date(match.group(1))
        upload.data_fim_periodo = _parse_date(match.group(2))

    # — Limpa dados anteriores deste upload —
    upload.agendas.all().delete()

    # — Percorre as linhas a partir da linha 10 —
    agenda_obj: Optional[ProducaoAgenda] = None
    total_agendas = 0
    total_medicos = 0

    for dados in sheet.iter_linhas():
        col_a = str(dados.get(COLUNAS_SIRESP[0], "")).strip()
        if not col_a:
            continue

        if _eh_total_geral(col_a):
            break

        if _eh_agenda(col_a):
            agenda_obj, _ = ProducaoAgenda.objects.get_or_create(
                upload=upload,
                nome_agenda=col_a,
            )
            _preencher_campos_numericos(agenda_obj, dados)
            agenda_obj.save()
            total_agendas += 1

        elif _eh_medico(col_a) and agenda_obj is not None:
            medico_obj = ProducaoMedico(
                agenda=agenda_obj,
                nome_medico=col_a,
            )
            _preencher_campos_numericos(medico_obj, dados)
            medico_obj.save()
            total_medicos += 1

    upload.total_agendas = total_agendas
    upload.total_medicos = total_medicos
    upload.status = StatusImportacao.CONFIRMADO
    upload.erro_processamento = ""
    upload.save()
