"""
Producao SIRESP — parser XLS/XLSX/HTML de Cirurgias/Exames exportado do SIRESP.

Estrutura esperada:
  B2   : "Período:DD-MM-AAAAaDD-MM-AAAA"
  Linha 8  : cabeçalhos (25 colunas, A–Y)
  Linha 9+ : dados

Diferenças em relação ao relatório de Consultas (producao_siresp.py):
  - Agendas são escritas em MAIÚSCULAS (identificadas por conjunto fixo AGENDAS_SIRESP_EXAMES)
  - Profissionais também em MAIÚSCULAS (identificados por exclusão do conjunto de agendas)
  - 25 colunas (A–Y); coluna N "Atendidos" → campo `presencial`
  - Sem colunas Teleconsulta e Total-Atendidos-2 (ficam com valor 0)
  - Dados a partir da linha 9 (cabeçalhos na linha 8)
  - No formato HTML (SIRESP): apenas 3 linhas de cabeçalho (vs. 4 no relatório de Consultas)

Formatos suportados:
  .xlsx / .xlsm         → openpyxl
  .xls (legado binário) → xlrd
  .xls (HTML disfarçado)→ pandas.read_html()
    O SIRESP exporta arquivos .xls que são HTML puro (ISO-8859-1).
    Detectados pelo primeiro byte '<' (0x3C).

Detecção automática por cabeçalho do arquivo, não pela extensão.
"""

import io
import re
from typing import Optional

import openpyxl
import pandas as pd
import xlrd

from .models import (
    UploadProducao, ProducaoAgenda, ProducaoMedico,
    StatusImportacao, COLUNAS_SIRESP_EXAMES,
)
from .producao_siresp import (
    _XLS_MAGIC, _HTML_MAGIC, _PERIODO_RE, _parse_date,
    _safe_int, _safe_float, _eh_total_geral, _preencher_campos_numericos,
)

# ---------------------------------------------------------------------------
# Lista canônica de agendas do relatório de Cirurgias/Exames
# ---------------------------------------------------------------------------

AGENDAS_SIRESP_EXAMES = {
    "020901002 - COLONOSCOPIA ALTA SUSPEIÇÃO - REGULADO",
    "040101 - PEQUENAS CIRURGIAS - PELE CMA",
    "AGULHAMENTO DE LESAO MAMARIA GUIADA POR MAMOGRAFIA - INTERNO",
    "AGULHAMENTO DE LESÃO MAMARIA GUIADO POR USG - INTERNO",
    "ANGIOGRAFIA FLUORESCENTE BINOCULAR - INTERNO",
    "ANGIOTOMOGRAFIA - EXTERNA",
    "ANGIOTOMOGRAFIA - INTERNA",
    "AUDIOMETRIA - EXTERNO",
    "AUDIOMETRIA - INTERNO",
    "AUDIOMETRIA COMPORTAMENTAL - EXTERNO",
    "AUDIOMETRIA COMPORTAMENTAL - INTERNO",
    "AVALIACAO URODINAMICA COMPLETA - EXTERNO",
    "AVALIACAO URODINAMICA COMPLETA - INTERNO",
    "BIOMETRIA ULTRASSONICA MONOCULAR - INTERNO",
    "CAMPIMETRIA COMPUTADORIZADA MONOCULAR - INTERNO",
    "CIRURGIA - BIOPSIA DE PROSTATA",
    "CIRURGIA - CIRURGIA GERAL - EXCISAO E RETALHO",
    "CIRURGIA - CIRURGIA GERAL - HERNIA",
    "CIRURGIA - CIRURGIA PEDIATRICA",
    "CIRURGIA - CIRURGIA PEDIATRICA - HERNIA",
    "CIRURGIA - CIRURGIA PLASTICA - EXCISAO E RETALHO",
    "CIRURGIA - CIRURGIA PLASTICA II - CMA",
    "CIRURGIA - CIRURGIA VASCULAR - VARIZES",
    "CIRURGIA - CISTOSCOPIA - URETEROSCOPIA E/OU URETROSCOPIA",
    "CIRURGIA - COLOPROCTOLOGIA",
    "CIRURGIA - DERMATOLOGIA",
    "CIRURGIA - INJECAO DE AFLIBERCETE (EYLIA) MONOCULAR - INTERNO",
    "CIRURGIA - MASTOLOGIA - SETORECTOMIA",
    "CIRURGIA - OFTALMOLOGIA",
    "CIRURGIA - OFTALMOLOGIA - BLEFAROCALASE",
    "CIRURGIA - OFTALMOLOGIA - CALAZIO",
    "CIRURGIA - OFTALMOLOGIA - CAPSULOTOMIA",
    "CIRURGIA - OFTALMOLOGIA - CATARATA",
    "CIRURGIA - OFTALMOLOGIA - EPILACAO A LASER",
    "CIRURGIA - OFTALMOLOGIA - FOTOCOAGULACAO A LASER BINOCULAR WILSON JUNIOR",
    "CIRURGIA - OFTALMOLOGIA - IRIDECTOMIA",
    "CIRURGIA - OFTALMOLOGIA - PTERIGIO",
    "CIRURGIA - ORTOPEDIA",
    "CIRURGIA - PAAF DE MAMA INTERNO - PUNÇÃO DE MAMA POR AGULHA GROSSA",
    "CIRURGIA - UROLOGIA",
    "CIRURGIA - UROLOGIA POSTECTOMIA",
    "CIRURGIA - UROLOGIA VASECTOMIA",
    "COLONOSCOPIA - EXTERNO",
    "COLONOSCOPIA - INTERNO",
    "COLONOSCOPIA PREPARO - MUNICÍPIOS",
    "ECOCARDIOGRAFIA - EXTERNO",
    "ECOCARDIOGRAFIA - INTERNO",
    "ECOCARDIOGRAFIA - LC HIPERTENSÃO",
    "ELETROCARDIOGRAMA - EXTERNO",
    "ELETROCARDIOGRAMA - INTERNO",
    "ELETROCARDIOGRAMA - LC HIPERTENSÃO",
    "ELETROENCEFALOGRAMA - EXTERNO",
    "ELETROENCEFALOGRAMA - INTERNO",
    "ENDOSCOPIA - EXTERNO",
    "ENDOSCOPIA - INTERNO",
    "HOLTER - EXTERNO",
    "HOLTER - INTERNO",
    "LABORATORIO - CEAC - HEMOGRAMA COMPLETO - INTERNO",
    "LABORATORIO - CEAC - LACTOSE, TESTE DE TOLERANCIA",
    "LABORATORIO - CEAC - LC HIPERTENSÃO",
    "LABORATORIO - CEAC - SAUDE DO HOMEM",
    "MAMOGRAFIA - EXTERNO",
    "MAMOGRAFIA - INTERNO",
    "MAMOGRAFIA RASTREAMENTO - PROGRAMA",
    "MAPA - EXTERNO",
    "MAPA - INTERNO",
    "MAPA - LC HIPERTENSÃO",
    "MICROSCOPIA ESPECULAR DE CORNEA MONOCULAR - INTERNO",
    "NASOFIBROSCOPIA - EXTERNO",
    "NASOFIBROSCOPIA - INTERNO",
    "PAQUIMETRIA (MONOCULAR) - INTERNO",
    "POTENCIAL DE ACUIDADE VISUAL MONOCULAR - INTERNO",
    "POTENCIAL EVOCADO AUDITIVO P/TRIAGEM AUDITIVA - EXTERNO",
    "POTENCIAL EVOCADO AUDITIVO P/TRIAGEM AUDITIVA - INTERNO",
    "PROVA DE FUNCAO PULMONAR SIMPLES - EXTERNO",
    "PROVA DE FUNCAO PULMONAR SIMPLES - INTERNO",
    "RAIO X - EXTERNO",
    "RAIO X - INTERNO",
    "RAIO-X - EXTRA",
    "RETINOGRAFIA COLORIDA BINOCULAR - INTERNO",
    "TESTE DE ESFORCO / TESTE ERGOMETRICO - EXTERNO",
    "TESTE DE ESFORCO / TESTE ERGOMETRICO - INTERNO",
    "TOMOGRAFIA - EXTERNO (ABD/PELVE)",
    "TOMOGRAFIA - EXTERNO (CR-ART-COL-PESC-MAST)",
    "TOMOGRAFIA - INTERNO (ABD/PELVE)",
    "TOMOGRAFIA - INTERNO (CR-ART-COL-PESC-MAST)",
    "TOMOGRAFIA COM SEDAÇÃO - INTERNA",
    "TOMOGRAFIA DE COERÊNCIA ÓPTICA - INTERNA",
    "TOPOGRAFIA COMPUTADORIZADA DE CORNEA MONOCULAR - INTERNO",
    "US DE GLOBO OCULAR / ORBITA - INTERNO",
    "US DOPPLER GERAL - INTERNO",
    "US DOPPLER VASCULAR - INTERNO",
    "US GERAL - EXTERNO",
    "US GERAL - INTERNO",
    "US MAMAS - EXTERNO",
    "US MAMAS - INTERNO",
    "US MUSCULO ESQUELETICO - EXTERNO",
    "US MUSCULO ESQUELETICO - INTERNO",
    "US OBSTETRICO - EXTERNO",
    "US PEDIATRICO - EXTERNO",
}

# Conjunto normalizado (sem espaços extras, maiúsculas) para matching robusto
_AGENDAS_UPPER = {nome.strip().upper() for nome in AGENDAS_SIRESP_EXAMES}


# ---------------------------------------------------------------------------
# Identificação de linhas
# ---------------------------------------------------------------------------

def _eh_agenda_exame(texto: str) -> bool:
    """True se o texto corresponde a uma agenda conhecida do relatório de Exames."""
    if not texto or len(texto) < 3:
        return False
    return texto.strip().upper() in _AGENDAS_UPPER


def _eh_profissional_exame(texto: str) -> bool:
    """True se o texto é um nome de profissional (all-caps, não é agenda nem rodapé)."""
    if not texto or len(texto) < 3:
        return False
    texto = texto.strip()
    if _eh_total_geral(texto):
        return False
    if _eh_agenda_exame(texto):
        return False
    letras = [c for c in texto if c.isalpha()]
    if not letras:
        return False
    return all(c.isupper() for c in letras)


# ---------------------------------------------------------------------------
# Adaptadores de formato — interface uniforme para XLS e XLSX
# (leitura a partir da linha 9, cabeçalhos na linha 8)
# ---------------------------------------------------------------------------

class _SheetXlsxExames:
    """Wrapper sobre openpyxl worksheet para o relatório de Exames."""

    def __init__(self, ws):
        self._ws = ws
        self.n_colunas = len(COLUNAS_SIRESP_EXAMES)

    def cell_b2(self) -> str:
        val = self._ws["B2"].value
        return str(val).strip() if val is not None else ""

    def iter_linhas(self):
        for row in self._ws.iter_rows(min_row=9, max_col=self.n_colunas):
            dados = {}
            for col_idx, cell in enumerate(row[:self.n_colunas]):
                nome = COLUNAS_SIRESP_EXAMES[col_idx]
                val = cell.value
                if val is None:
                    val = ""
                elif isinstance(val, str):
                    val = val.strip()
                dados[nome] = val
            yield dados


class _SheetXlsExames:
    """Wrapper sobre xlrd sheet para o relatório de Exames."""

    def __init__(self, sheet):
        self._sheet = sheet
        self.n_colunas = len(COLUNAS_SIRESP_EXAMES)

    def cell_b2(self) -> str:
        return str(self._sheet.cell_value(1, 1)).strip()

    def iter_linhas(self):
        sheet = self._sheet
        n = min(self.n_colunas, sheet.ncols)
        for row_idx in range(8, sheet.nrows):  # linha 9 em base-1 = índice 8
            dados = {}
            for col_idx in range(n):
                nome = COLUNAS_SIRESP_EXAMES[col_idx]
                raw = sheet.cell_value(row_idx, col_idx)
                if isinstance(raw, str):
                    raw = raw.strip()
                dados[nome] = raw
            yield dados


class _SheetHtmlExames:
    """
    Wrapper para arquivos .xls de Cirurgias/Exames exportados pelo SIRESP
    que são documentos HTML (ISO-8859-1) disfarçados de XLS.

    Diferença crítica em relação ao relatório de Consultas:
      - Apenas 3 linhas de cabeçalho hierárquico (vs. 4 em Consultas)
      - Dados começam na linha de índice 3 (após pular os 3 cabeçalhos)
    """

    _N_CABECALHOS = 3

    def __init__(self, conteudo: bytes):
        html = conteudo.decode("iso-8859-1", errors="replace")
        self._tables = pd.read_html(
            io.StringIO(html),
            header=None,
            thousands=".",
            decimal=",",
        )
        self._tabela_principal = max(self._tables, key=len)
        self.n_colunas = len(COLUNAS_SIRESP_EXAMES)

    def cell_b2(self) -> str:
        """Varre as tabelas de metadados em busca do campo 'Período:'."""
        for table in self._tables:
            for valor in table.values.flatten():
                if isinstance(valor, str) and "Período:" in valor:
                    return valor
        return ""

    def iter_linhas(self):
        """Itera os dados após os 3 cabeçalhos hierárquicos do SIRESP."""
        df = self._tabela_principal.iloc[self._N_CABECALHOS:].reset_index(drop=True)
        n = min(self.n_colunas, df.shape[1])
        for _, row in df.iterrows():
            dados = {}
            for col_idx in range(n):
                nome = COLUNAS_SIRESP_EXAMES[col_idx]
                val = row.iloc[col_idx]
                if pd.isna(val):
                    val = ""
                elif not isinstance(val, str):
                    val = str(val)
                dados[nome] = val
            yield dados


def _abrir_sheet_exames(conteudo: bytes):
    """
    Detecta o formato pelo cabeçalho do arquivo e retorna o wrapper correto.

      HTML (SIRESP): primeiro byte == '<'            → _SheetHtmlExames
      XLS   (BIFF) : primeiros 8 bytes == _XLS_MAGIC → _SheetXlsExames
      Qualquer outro caso (ZIP/OOXML)               → _SheetXlsxExames
    """
    if conteudo[:1] == _HTML_MAGIC:
        return _SheetHtmlExames(conteudo)
    elif conteudo[:8] == _XLS_MAGIC:
        wb = xlrd.open_workbook(file_contents=conteudo)
        return _SheetXlsExames(wb.sheets()[0])
    else:
        wb = openpyxl.load_workbook(filename=io.BytesIO(conteudo), data_only=True)
        return _SheetXlsxExames(wb.active)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def processar_upload_exames(upload_id: int) -> None:
    """
    Lê o arquivo XLS/XLSX de Cirurgias/Exames e persiste
    ProducaoAgenda + ProducaoMedico no banco.

    Agendas são identificadas pelo conjunto fixo AGENDAS_SIRESP_EXAMES;
    profissionais são as demais linhas em MAIÚSCULAS entre duas agendas.
    """
    upload = UploadProducao.objects.get(pk=upload_id)

    with upload.arquivo.open("rb") as f:
        conteudo = f.read()

    sheet = _abrir_sheet_exames(conteudo)

    match = _PERIODO_RE.search(sheet.cell_b2())
    if match:
        upload.data_inicio_periodo = _parse_date(match.group(1))
        upload.data_fim_periodo = _parse_date(match.group(2))

    upload.agendas.all().delete()

    agenda_obj: Optional[ProducaoAgenda] = None
    total_agendas = 0
    total_medicos = 0

    for dados in sheet.iter_linhas():
        col_a = str(dados.get(COLUNAS_SIRESP_EXAMES[0], "")).strip()
        if not col_a:
            continue

        if _eh_total_geral(col_a):
            break

        if _eh_agenda_exame(col_a):
            agenda_obj, _ = ProducaoAgenda.objects.get_or_create(
                upload=upload,
                nome_agenda=col_a,
            )
            _preencher_campos_numericos(agenda_obj, dados)
            agenda_obj.save()
            total_agendas += 1

        elif _eh_profissional_exame(col_a) and agenda_obj is not None:
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
