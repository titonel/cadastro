"""
extrator.py – Extrai dados estruturados de contratos PDF do padrão SECONCI/AME.

Campos extraídos:
  - razao_social       : razão social da contratada
  - cnpj               : CNPJ da contratada
  - objeto             : descrição do objeto do contrato (cláusula 1.1)
  - servicos           : lista de serviços com descrição, qtde, valor unitário, unidade
  - data_assinatura    : data de assinatura (= data início do contrato)
  - data_fim           : prazo final calculado a partir da vigência em meses
  - meses_vigencia     : número de meses de vigência
  - valor_mensal       : valor estimado mensal
  - valor_global       : valor global estimado
  - numero_processo    : número do processo (Nº do processo)
"""

import re
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def _mes_pt(nome: str) -> int:
    meses = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
        "abril": 4, "maio": 5, "junho": 6, "julho": 7,
        "agosto": 8, "setembro": 9, "outubro": 10,
        "novembro": 11, "dezembro": 12,
    }
    return meses.get(nome.lower().strip(), 0)


def _parse_data_pt(texto: str) -> date | None:
    """Converte strings como '01 de agosto de 2026' ou '01/08/2026' em date."""
    # Formato extenso: 01 de agosto de 2026
    m = re.search(
        r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})",
        texto, re.IGNORECASE
    )
    if m:
        dia, mes_nome, ano = int(m.group(1)), m.group(2), int(m.group(3))
        mes = _mes_pt(mes_nome)
        if mes:
            return date(ano, mes, dia)
    # Formato numérico: 01/08/2026
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", texto)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def _limpar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def _extrair_texto_pdf(caminho_pdf) -> str:
    """Extrai texto completo do PDF usando pdfplumber."""
    if not HAS_PDFPLUMBER:
        raise ImportError(
            "pdfplumber não está instalado. Execute: pip install pdfplumber"
        )
    texto = []
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            t = pagina.extract_text()
            if t:
                texto.append(t)
    return "\n".join(texto)


# ---------------------------------------------------------------------------
# Extratores individuais
# ---------------------------------------------------------------------------

def _extrair_numero_processo(texto: str) -> str:
    m = re.search(r"N[ºo°\.]+\s*do\s*processo[:\s]+([\d]+)", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # formato alternativo no topo: "1527 – ID: 9164"
    m = re.search(r"(\d{3,6})\s*[–-]\s*ID[:\s]*(\d+)", texto)
    if m:
        return m.group(1).strip()
    return ""


def _extrair_razao_social(texto: str) -> str:
    """
    Padrão: 'Pelo presente instrumento, RAZAO SOCIAL LTDA/ME/SA, inscrita'
    ou      'RAZAO SOCIAL LTDA, inscrito no CNPJ'
    """
    # Padrão V14 (novo formato)
    m = re.search(
        r"instrumento,\s+([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-ZÁÀÃÂÉÊÍÓÔÕÚÇÇ\s\-\.]{2,80}?)\s*,?\s*inscrit",
        texto, re.IGNORECASE
    )
    if m:
        return _limpar(m.group(1))
    # Padrão "CONTRATADO(A)  Nome: Fulano"
    m = re.search(r"CONTRATADO\s*\(A\)\s*Nome:\s*(.+)", texto)
    if m:
        return _limpar(m.group(1))
    return ""


def _extrair_cnpj(texto: str) -> str:
    m = re.search(
        r"CNPJ\s*(?:n[ºo°\.]+|sob\s+o\s+n[ºo°\.]+)?\s*[:\s]*([\d]{2}[\.\/]?[\d]{3}[\.\/]?[\d]{3}[\.\/]?[\d]{4}[-\s]?[\d]{2})",
        texto, re.IGNORECASE
    )
    if m:
        raw = re.sub(r"\s", "", m.group(1))
        # Formata se vier sem pontuação
        if re.match(r"^\d{14}$", raw):
            raw = f"{raw[:2]}.{raw[2:5]}.{raw[5:8]}/{raw[8:12]}-{raw[12:]}"
        return raw
    return ""


def _extrair_objeto(texto: str) -> str:
    """
    Extrai o texto da cláusula 1.1 — objeto do contrato.
    """
    m = re.search(
        r"1\.1[\s\S]{0,20}?(?:objeto|constitui objeto)[\s\S]{0,10}?contrat(?:o|ação)[\s\S]{0,20}?(?:é a|é)?\s+([^\n]{20,400})",
        texto, re.IGNORECASE
    )
    if m:
        return _limpar(m.group(1))
    # Fallback: pega tudo entre '1.1' e '1.2'
    m = re.search(r"1\.1(.+?)1\.2", texto, re.DOTALL)
    if m:
        trecho = _limpar(m.group(1))
        return trecho[:400]
    return ""


def _extrair_servicos(texto: str) -> list[dict]:
    """
    Extrai linhas da tabela de serviços da cláusula 3.1.
    Retorna lista de dicts com: descricao, unidade, quantidade, valor_unitario, valor_total.
    """
    servicos = []

    # Tenta encontrar o bloco da tabela de preços na seção 3.1
    m = re.search(r"3\.1.+?Valor\s+estimado\s+mensal", texto, re.DOTALL | re.IGNORECASE)
    bloco = m.group(0) if m else texto

    # Padrão: linha com número, descrição, valor unit e valor total
    # Ex: "48 Consulta 62,40 2.995,20"
    padrao_linha = re.compile(
        r"(\d+)\s+(Consulta|Laudo|Exame|MAPA|HOLTER|Eletrocardiograma|Cirurgia[\w\s]*)"
        r"\s+([\d\.]+,\d{2})\s+([\d\.]+,\d{2})",
        re.IGNORECASE
    )
    for m in padrao_linha.finditer(bloco):
        qtde = int(m.group(1))
        descricao = m.group(2).strip()
        v_unit = float(m.group(3).replace(".", "").replace(",", "."))
        v_total = float(m.group(4).replace(".", "").replace(",", "."))
        servicos.append({
            "descricao": descricao,
            "unidade": descricao,
            "quantidade": qtde,
            "valor_unitario": v_unit,
            "valor_total": v_total,
        })

    # Fallback: tenta extrair pares valor unitário / valor total isolados
    if not servicos:
        padrao_valor = re.compile(
            r"([A-Za-záàãâéêíóôõúçÁÀÃÂÉÊÍÓÔÕÚÇ][\w\s]{2,40})\s+(\d+)\s+([\d\.]+,\d{2})\s+([\d\.]+,\d{2})",
            re.IGNORECASE
        )
        for m in padrao_valor.finditer(bloco):
            v_unit = float(m.group(3).replace(".", "").replace(",", "."))
            v_total = float(m.group(4).replace(".", "").replace(",", "."))
            servicos.append({
                "descricao": m.group(1).strip(),
                "unidade": m.group(1).strip(),
                "quantidade": int(m.group(2)),
                "valor_unitario": v_unit,
                "valor_total": v_total,
            })

    return servicos


def _extrair_valor_mensal(texto: str) -> float:
    m = re.search(
        r"valor\s+estimado\s+mensal\s+(?:de\s+)?R\$\s*([\d\.]+,[\d]{2})",
        texto, re.IGNORECASE
    )
    if m:
        return float(m.group(1).replace(".", "").replace(",", "."))
    # Tenta capturar o valor ao lado de 'Valor estimado mensal' na tabela
    m = re.search(
        r"Valor\s+estimado\s+mensal[\s\S]{0,30}?([\d\.]+,[\d]{2})",
        texto, re.IGNORECASE
    )
    if m:
        return float(m.group(1).replace(".", "").replace(",", "."))
    return 0.0


def _extrair_valor_global(texto: str) -> float:
    m = re.search(
        r"valor\s+(?:global\s+)?estimado\s+de\s+R\$\s*([\d\.]+,[\d]{2})",
        texto, re.IGNORECASE
    )
    if m:
        return float(m.group(1).replace(".", "").replace(",", "."))
    return 0.0


def _extrair_vigencia(texto: str) -> tuple[date | None, date | None, int]:
    """
    Extrai data de início, data fim e meses de vigência.
    Padrões buscados:
      - 'vigorará pelo prazo de 60 (sessenta) meses, contados a partir de 01/08/2026'
      - 'São Paulo, 01 de agosto de 2026' (data de assinatura)
    """
    data_inicio = None
    data_fim = None
    meses = 0

    # Extrai meses de vigência
    m = re.search(
        r"prazo\s+de\s+(\d+)\s*\([\w\s]+\)\s*meses",
        texto, re.IGNORECASE
    )
    if m:
        meses = int(m.group(1))

    # Data início: 'contados a partir de DD/MM/AAAA' ou 'a partir de DD de mês de AAAA'
    m = re.search(
        r"a\s+partir\s+de\s+(.{5,30}?)(?:,|\.|\n|correspondente)",
        texto, re.IGNORECASE
    )
    if m:
        data_inicio = _parse_data_pt(m.group(1))

    # Fallback: data de assinatura no rodapé 'São Paulo, DD de mês de AAAA'
    if not data_inicio:
        m = re.search(
            r"S[ãa]o\s+Paulo,\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})",
            texto, re.IGNORECASE
        )
        if m:
            data_inicio = _parse_data_pt(m.group(1))

    # Calcula data fim
    if data_inicio and meses:
        data_fim = data_inicio + relativedelta(months=meses)

    return data_inicio, data_fim, meses


def _extrair_especialidade(texto: str) -> str:
    """
    Extrai a especialidade médica mencionada no objeto ou na tabela de serviços.
    """
    especialidades_conhecidas = [
        "Pneumologia Pediátrica", "Pneumologia Pediatrica",
        "Cardiologia", "Oftalmologia", "Gastroenterologia",
        "Ortopedia", "Neurologia", "Endocrinologia", "Dermatologia",
        "Urologia", "Ginecologia", "Obstetrícia", "Reumatologia",
        "Oncologia", "Hematologia", "Nefrologia", "Infectologia",
        "Psiquiatria", "Pediatria", "Geriatria", "Cirurgia Geral",
        "Otorrinolaringologia", "Proctologia", "Angiologia",
        "Mastologia", "Cirurgia Vascular",
    ]
    for esp in especialidades_conhecidas:
        if esp.lower() in texto.lower():
            # Normaliza Pediatrica → Pediátrica
            return esp.replace("Pediatrica", "Pediátrica")
    return ""


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def extrair_contrato(caminho_pdf) -> dict:
    """
    Extrai dados de um contrato PDF no padrão SECONCI/AME.

    Retorna dict com:
      razao_social, cnpj, objeto, servicos, especialidade,
      data_assinatura, data_fim, meses_vigencia,
      valor_mensal, valor_global, numero_processo, erro (None se OK)
    """
    resultado = {
        "razao_social": "",
        "cnpj": "",
        "objeto": "",
        "servicos": [],
        "especialidade": "",
        "data_assinatura": None,
        "data_fim": None,
        "meses_vigencia": 0,
        "valor_mensal": 0.0,
        "valor_global": 0.0,
        "numero_processo": "",
        "erro": None,
    }

    try:
        texto = _extrair_texto_pdf(caminho_pdf)
    except Exception as e:
        resultado["erro"] = f"Falha ao ler PDF: {e}"
        return resultado

    try:
        resultado["numero_processo"] = _extrair_numero_processo(texto)
        resultado["razao_social"] = _extrair_razao_social(texto)
        resultado["cnpj"] = _extrair_cnpj(texto)
        resultado["objeto"] = _extrair_objeto(texto)
        resultado["servicos"] = _extrair_servicos(texto)
        resultado["especialidade"] = _extrair_especialidade(texto)
        resultado["valor_mensal"] = _extrair_valor_mensal(texto)
        resultado["valor_global"] = _extrair_valor_global(texto)

        data_inicio, data_fim, meses = _extrair_vigencia(texto)
        resultado["data_assinatura"] = data_inicio
        resultado["data_fim"] = data_fim
        resultado["meses_vigencia"] = meses

    except Exception as e:
        resultado["erro"] = f"Erro durante extração: {e}"

    return resultado
