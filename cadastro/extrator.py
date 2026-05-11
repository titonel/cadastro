"""
extrator.py – Extrai dados estruturados de contratos PDF do padrão SECONCI/AME.
"""

import re
from datetime import date
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
        "janeiro": 1, "fevereiro": 2, "mar\u00e7o": 3, "marco": 3,
        "abril": 4, "maio": 5, "junho": 6, "julho": 7,
        "agosto": 8, "setembro": 9, "outubro": 10,
        "novembro": 11, "dezembro": 12,
    }
    return meses.get(nome.lower().strip(), 0)


def _parse_data_pt(texto: str) -> date | None:
    m = re.search(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", texto, re.IGNORECASE)
    if m:
        dia, mes_nome, ano = int(m.group(1)), m.group(2), int(m.group(3))
        mes = _mes_pt(mes_nome)
        if mes:
            return date(ano, mes, dia)
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", texto)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def _limpar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def _extrair_texto_pdf(caminho_pdf) -> str:
    if not HAS_PDFPLUMBER:
        raise ImportError("pdfplumber n\u00e3o est\u00e1 instalado. Execute: pip install pdfplumber")
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
    m = re.search(r"N[\u00bao\u00b0\.]+\s*do\s*processo[:\s]+([\d]+)", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"(\d{3,6})\s*[\u2013-]\s*ID[:\s]*(\d+)", texto)
    if m:
        return m.group(1).strip()
    return ""


def _extrair_razao_social(texto: str) -> str:
    """
    Extrai a raz\u00e3o social da contratada.
    Padr\u00e3o principal: 'Pelo presente instrumento, RAZAO SOCIAL, inscrita'
    """
    m = re.search(
        r"instrumento,\s+([A-Z\u00c1\u00c0\u00c3\u00c2\u00c9\u00ca\u00cd\u00d3\u00d4\u00d5\u00da\u00c7][A-Z\u00c1\u00c0\u00c3\u00c2\u00c9\u00ca\u00cd\u00d3\u00d4\u00d5\u00da\u00c7\s\-\.]{2,80}?)\s*,?\s*inscrit",
        texto, re.IGNORECASE
    )
    if m:
        return _limpar(m.group(1))
    return ""


def _extrair_cnpj(texto: str) -> str:
    """
    Extrai o CNPJ da contratada (primeiro CNPJ que aparece no texto,
    que pertence \u00e0 contratada, n\u00e3o ao SECONCI).
    """
    matches = re.findall(
        r"CNPJ\s*(?:n[\u00bao\u00b0\.]+|sob\s+o\s+n[\u00bao\u00b0\.]+)?\s*[:\s]*([\d]{2}[\.\/]?[\d]{3}[\.\/]?[\d]{3}[\.\/]?[\d]{4}[-\s]?[\d]{2})",
        texto, re.IGNORECASE
    )
    if matches:
        raw = re.sub(r"\s", "", matches[0])
        if re.match(r"^\d{14}$", raw):
            raw = f"{raw[:2]}.{raw[2:5]}.{raw[5:8]}/{raw[8:12]}-{raw[12:]}"
        return raw
    return ""


def _extrair_objeto(texto: str) -> str:
    """
    Extrai o objeto real do contrato a partir da cl\u00e1usula 1.1.
    Captura o que vem ap\u00f3s 'empresa especializada na presta\u00e7\u00e3o de '
    ou ap\u00f3s 'servi\u00e7os de ' na cl\u00e1usula 1.1.
    Exemplos:
      'servi\u00e7os m\u00e9dicos de Pneumologia Pedi\u00e1trica'
      'servi\u00e7os de Cardiologia'
    """
    # Padr\u00e3o principal: captura tudo ap\u00f3s 'presta\u00e7\u00e3o de ' ou 'servi\u00e7os de '
    # dentro do trecho da cl\u00e1usula 1.1
    bloco_11 = ""
    m = re.search(r"1\.1.+?1\.2", texto, re.DOTALL)
    if m:
        bloco_11 = m.group(0)
    else:
        # Sem 1.2, pega at\u00e9 300 chars ap\u00f3s 1.1
        m = re.search(r"1\.1.{0,300}", texto, re.DOTALL)
        if m:
            bloco_11 = m.group(0)

    if bloco_11:
        # Tenta capturar ap\u00f3s 'presta\u00e7\u00e3o de servi\u00e7os de ' ou 'presta\u00e7\u00e3o de '
        m = re.search(
            r"presta[\u00e7c][\u00e3a]o\s+de\s+servi[\u00e7c]os\s+(?:m[\u00e9e]dicos\s+)?de\s+([^\n\.]{5,200})",
            bloco_11, re.IGNORECASE
        )
        if m:
            return _limpar(m.group(1)).rstrip(".")

        m = re.search(
            r"presta[\u00e7c][\u00e3a]o\s+de\s+([^\n\.]{5,200})",
            bloco_11, re.IGNORECASE
        )
        if m:
            return _limpar(m.group(1)).rstrip(".")

        # Fallback: texto completo entre 1.1 e 1.2 limpo
        return _limpar(bloco_11.replace("1.1", "").replace("1.2", ""))[:300].rstrip(".")

    return ""


def _extrair_representante_legal(texto: str) -> tuple[str, str]:
    """
    Extrai nome e CPF do representante legal a partir do quadro de assinaturas.
    Padr\u00e3o: 'CONTRATADO (A) Nome: Fulano de Tal CPF: 000.000.000-00'
    """
    nome = ""
    cpf = ""

    # Captura o bloco do CONTRATADO(A) no quadro de assinaturas
    m = re.search(
        r"CONTRATADO\s*\(A\)[\s\S]{0,20}?Nome[:\s]+([^\n]{3,80})[\s\S]{0,30}?CPF[:\s]+([\d]{3}[\. ]?[\d]{3}[\. ]?[\d]{3}[-\. ]?[\d]{2})",
        texto, re.IGNORECASE
    )
    if m:
        nome = _limpar(m.group(1))
        cpf_raw = re.sub(r"[^\d]", "", m.group(2))
        if len(cpf_raw) == 11:
            cpf = f"{cpf_raw[:3]}.{cpf_raw[3:6]}.{cpf_raw[6:9]}-{cpf_raw[9:]}"
        else:
            cpf = m.group(2).strip()
        return nome, cpf

    # Fallback: bloco de assinatura com nome e CPF em linhas separadas
    m = re.search(
        r"CONTRATADO\s*\(A\)[\s\S]{0,60}?Nome:\s*([^\n]+)[\s\S]{0,20}?CPF:\s*([\d\. -]{11,14})",
        texto, re.IGNORECASE
    )
    if m:
        nome = _limpar(m.group(1))
        cpf_raw = re.sub(r"[^\d]", "", m.group(2))
        if len(cpf_raw) == 11:
            cpf = f"{cpf_raw[:3]}.{cpf_raw[3:6]}.{cpf_raw[6:9]}-{cpf_raw[9:]}"
        else:
            cpf = m.group(2).strip()

    return nome, cpf


def _extrair_servicos(texto: str) -> list[dict]:
    servicos = []
    m = re.search(r"3\.1.+?Valor\s+estimado\s+mensal", texto, re.DOTALL | re.IGNORECASE)
    bloco = m.group(0) if m else texto

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

    if not servicos:
        padrao_valor = re.compile(
            r"([A-Za-z\u00e1\u00e0\u00e3\u00e2\u00e9\u00ea\u00ed\u00f3\u00f4\u00f5\u00fa\u00e7][\w\s]{2,40})\s+(\d+)\s+([\d\.]+,\d{2})\s+([\d\.]+,\d{2})",
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
    data_inicio = None
    data_fim = None
    meses = 0

    m = re.search(r"prazo\s+de\s+(\d+)\s*\([\w\s]+\)\s*meses", texto, re.IGNORECASE)
    if m:
        meses = int(m.group(1))

    m = re.search(
        r"a\s+partir\s+de\s+(.{5,30}?)(?:,|\.|\n|correspondente)",
        texto, re.IGNORECASE
    )
    if m:
        data_inicio = _parse_data_pt(m.group(1))

    if not data_inicio:
        m = re.search(
            r"S[\u00e3a]o\s+Paulo,\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})",
            texto, re.IGNORECASE
        )
        if m:
            data_inicio = _parse_data_pt(m.group(1))

    if data_inicio and meses:
        data_fim = data_inicio + relativedelta(months=meses)

    return data_inicio, data_fim, meses


def _extrair_especialidade(texto: str) -> str:
    especialidades_conhecidas = [
        "Pneumologia Pedi\u00e1trica", "Pneumologia Pediatrica",
        "Cardiologia", "Oftalmologia", "Gastroenterologia",
        "Ortopedia", "Neurologia", "Endocrinologia", "Dermatologia",
        "Urologia", "Ginecologia", "Obstetr\u00edcia", "Reumatologia",
        "Oncologia", "Hematologia", "Nefrologia", "Infectologia",
        "Psiquiatria", "Pediatria", "Geriatria", "Cirurgia Geral",
        "Otorrinolaringologia", "Proctologia", "Angiologia",
        "Mastologia", "Cirurgia Vascular",
    ]
    for esp in especialidades_conhecidas:
        if esp.lower() in texto.lower():
            return esp.replace("Pediatrica", "Pedi\u00e1trica")
    return ""


# ---------------------------------------------------------------------------
# Fun\u00e7\u00e3o principal
# ---------------------------------------------------------------------------

def extrair_contrato(caminho_pdf) -> dict:
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
        "nome_representante": "",
        "cpf_representante": "",
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

        nome_rep, cpf_rep = _extrair_representante_legal(texto)
        resultado["nome_representante"] = nome_rep
        resultado["cpf_representante"] = cpf_rep

        data_inicio, data_fim, meses = _extrair_vigencia(texto)
        resultado["data_assinatura"] = data_inicio
        resultado["data_fim"] = data_fim
        resultado["meses_vigencia"] = meses

    except Exception as e:
        resultado["erro"] = f"Erro durante extra\u00e7\u00e3o: {e}"

    return resultado
