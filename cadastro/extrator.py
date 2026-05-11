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
        "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
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
        raise ImportError("pdfplumber não está instalado. Execute: pip install pdfplumber")
    texto = []
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            t = pagina.extract_text()
            if t:
                texto.append(t)
    return "\n".join(texto)


def _localizar_anexo1(texto: str) -> str:
    """
    Retorna o trecho do texto a partir do "ANEXO 1" (Condições Específicas),
    pois é nessa seção que ficam os dados mais confiáveis da contratada.
    Se não encontrar, retorna o texto completo.
    """
    m = re.search(r"ANEXO\s+1\b", texto, re.IGNORECASE)
    if m:
        return texto[m.start():]
    return texto


# ---------------------------------------------------------------------------
# Extratores individuais
# ---------------------------------------------------------------------------

def _extrair_numero_processo(texto: str) -> str:
    m = re.search(r"N[°º\.]+\s*do\s*processo[:\s]+([\d]+)", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"(\d{3,6})\s*[–-]\s*ID[:\s]*(\d+)", texto)
    if m:
        return m.group(1).strip()
    return ""


def _extrair_razao_social(texto: str) -> str:
    """
    Extrai a razão social da contratada.

    Estratégia (em ordem de prioridade):
    1. Padrão "Pelo presente, RAZAO SOCIAL, inscrito no CNPJ" – usado no
       Termo de Adesão deste modelo SECONCI.
    2. Padrão "instrumento, RAZAO SOCIAL, inscrita" – usado em outros modelos.
    3. Padrão do Anexo 1: "SECONCI-SP, gestor ... e RAZAO SOCIAL, doravante"
    """
    # Padrão 1 – Termo de Adesão: "presente, RAZAO SOCIAL, inscrito no CNPJ"
    m = re.search(
        r"presente,\s+([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-ZÁÀÃÂÉÊÍÓÔÕÚÇ\s\-\.]{2,80}?)\s*,\s*inscrit",
        texto, re.IGNORECASE
    )
    if m:
        return _limpar(m.group(1))

    # Padrão 2 – outros modelos
    m = re.search(
        r"instrumento,\s+([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-ZÁÀÃÂÉÊÍÓÔÕÚÇ\s\-\.]{2,80}?)\s*,?\s*inscrit",
        texto, re.IGNORECASE
    )
    if m:
        return _limpar(m.group(1))

    # Padrão 3 – Anexo 1: "gestor do AME ... e RAZAO SOCIAL, doravante"
    m = re.search(
        r"AME\s+CARAGUATATUBA\s+e\s+([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-ZÁÀÃÂÉÊÍÓÔÕÚÇ\s\-\.]{2,80}?)\s*,\s*doravante",
        texto, re.IGNORECASE
    )
    if m:
        return _limpar(m.group(1))

    return ""


def _extrair_cnpj(texto: str) -> str:
    """
    Extrai o CNPJ da contratada (primeiro CNPJ que aparece no texto,
    que pertence à contratada, não ao SECONCI).
    """
    matches = re.findall(
        r"CNPJ\s*(?:n[°º\.]+|sob\s+o\s+n[°º\.]+)?\s*[:\s]*([\d]{2}[\.\/ ]?[\d]{3}[\.\/ ]?[\d]{3}[\.\/ ]?[\d]{4}[-\s]?[\d]{2})",
        texto, re.IGNORECASE
    )
    if matches:
        raw = re.sub(r"\s", "", matches[0])
        if re.match(r"^\d{14}$", raw):
            raw = f"{raw[:2]}.{raw[2:5]}.{raw[5:8]}/{raw[8:12]}-{raw[12:]}"
        return raw
    return ""


def _extrair_inscricao_municipal(texto: str) -> str:
    """
    Extrai a Inscrição Municipal da contratada.
    Padrão: 'Inscrição Municipal Sob N.º 4.642.460-1' ou 'Insc. Municipal nº ...'
    """
    m = re.search(
        r"Inscri[çc][ãa]o\s+Municipal\s+[Ss]ob\s+N[.º°]+\s*([\d\.\-]+)",
        texto, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()
    m = re.search(
        r"Insc(?:ri[çc][ãa]o)?[\.]?\s+Municipal\s+(?:n[°º.]+)?\s*:?\s*([\d\.\-]+)",
        texto, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()
    return ""


def _extrair_endereco(texto: str) -> dict:
    """
    Extrai os campos de endereço da contratada a partir da linha do Termo de Adesão.

    Formato típico:
    "estabelecida na Rua Bertioga, 160 Apto 94 - Chácara Inglesa, CEP: 04.141-100,
     no município de São Paulo, Estado de São Paulo"

    Retorna dicionário com: logradouro, numero, complemento, bairro, cep, cidade.
    """
    resultado = {
        "logradouro": "",
        "numero": "",
        "complemento": "",
        "bairro": "",
        "cep": "",
        "cidade": "",
    }

    # Captura o trecho entre 'estabelecida na' e 'Estado de' (ou 'Doravante')
    m = re.search(
        r"estabelecida\s+na\s+(.+?)(?:,\s*no\s+munic[íi]pio|Doravante|DECLARA)",
        texto, re.IGNORECASE | re.DOTALL
    )
    if not m:
        return resultado

    bloco = _limpar(m.group(1))

    # CEP: '04.141-100' ou '04141-100' ou '04141100'
    cep_m = re.search(r"CEP[:\s]+([\d]{2}\.?[\d]{3}[-–][\d]{3})", bloco, re.IGNORECASE)
    if cep_m:
        resultado["cep"] = cep_m.group(1).strip()
        bloco_sem_cep = bloco[:cep_m.start()].strip().rstrip(",")
    else:
        cep_m = re.search(r"([\d]{5}[-–][\d]{3})", bloco)
        if cep_m:
            resultado["cep"] = cep_m.group(1)
            bloco_sem_cep = bloco[:cep_m.start()].strip().rstrip(",")
        else:
            bloco_sem_cep = bloco

    # Cidade: após 'município de'
    cidade_m = re.search(r"munic[íi]pio\s+de\s+([\w\s]+?)(?:,|$)", texto, re.IGNORECASE)
    if cidade_m:
        resultado["cidade"] = _limpar(cidade_m.group(1))

    # Tenta decompor "Logradouro, numero complemento - bairro"
    # Exemplo: "Rua Bertioga, 160 Apto 94 - Chácara Inglesa"
    m2 = re.match(
        r"^([^,]+),\s*(\d+[\w\s]*)(?:\s*[-–]\s*(.+))?$",
        bloco_sem_cep
    )
    if m2:
        resultado["logradouro"] = _limpar(m2.group(1))
        num_comp = _limpar(m2.group(2))
        bairro_raw = _limpar(m2.group(3)) if m2.group(3) else ""

        # Separa número de complemento dentro do grupo 2
        num_m = re.match(r"^(\d+)\s*(.*)", num_comp)
        if num_m:
            resultado["numero"] = num_m.group(1)
            resultado["complemento"] = _limpar(num_m.group(2))
        else:
            resultado["numero"] = num_comp

        resultado["bairro"] = bairro_raw
    else:
        resultado["logradouro"] = bloco_sem_cep

    return resultado


def _extrair_objeto(texto: str) -> str:
    """
    Extrai o objeto do contrato a partir da cláusula 1.1 do Anexo 1.
    """
    bloco_11 = ""
    m = re.search(r"1\.1.+?1\.2", texto, re.DOTALL)
    if m:
        bloco_11 = m.group(0)
    else:
        m = re.search(r"1\.1.{0,300}", texto, re.DOTALL)
        if m:
            bloco_11 = m.group(0)

    if bloco_11:
        m = re.search(
            r"presta[çc][ãa]o\s+de\s+servi[çc]os\s+(?:m[ée]dicos\s+)?de\s+([^\n\.]{5,200})",
            bloco_11, re.IGNORECASE
        )
        if m:
            return _limpar(m.group(1)).rstrip(".")

        m = re.search(
            r"presta[çc][ãa]o\s+de\s+([^\n\.]{5,200})",
            bloco_11, re.IGNORECASE
        )
        if m:
            return _limpar(m.group(1)).rstrip(".")

        return _limpar(bloco_11.replace("1.1", "").replace("1.2", ""))[:300].rstrip(".")

    return ""


def _extrair_representante_tecnico(texto: str) -> tuple[str, str]:
    """
    Extrai nome e CPF do responsável técnico (CONTRATADO(A)) a partir do
    Termo de Adesão ou das Disposições Finais.

    O documento SECONCI apresenta o campo assim:
        CONTRATADO (A)
        Nome: Fulano de Tal
        CPF: 000.000.000-00

    OU em linha única:
        CONTRATADO(A) Nome: Fulano CPF: 000...

    Tentativas em ordem:
    1. Linha "CONTRATADO (A)" com 'Nome:' e 'CPF:' nas linhas seguintes
       (captura multi-linha tolerante a espaços/quebras).
    2. Variação com parênteses: 'Contratado(a)'.
    3. Fallback: qualquer ocorrência de CPF próxima ao bloco CONTRATADO.
    """
    nome = ""
    cpf = ""

    # Padrão 1 – multilinhas com espaço: "CONTRATADO (A)" ... "Nome: X" ... "CPF: Y"
    for pat in [
        r"CONTRATADO\s*\(A\)[\s\S]{0,60}?Nome[:\s]+([^\n\r]{3,80}?)[\s\S]{0,60}?CPF[:\s]+([\d]{3}[\. ]?[\d]{3}[\. ]?[\d]{3}[-\. ]?[\d]{2})",
        r"Contratado\s*\(a\)[\s\S]{0,60}?Nome[:\s]+([^\n\r]{3,80}?)[\s\S]{0,60}?CPF[:\s]+([\d]{3}[\. ]?[\d]{3}[\. ]?[\d]{3}[-\. ]?[\d]{2})",
    ]:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            nome_raw = _limpar(m.group(1))
            cpf_raw = re.sub(r"[^\d]", "", m.group(2))
            # Descarta se o "nome" capturado é na verdade uma linha de CPF vazia ou só espaços
            if nome_raw and not re.match(r'^[\d\s\.\-]+$', nome_raw):
                nome = nome_raw
                if len(cpf_raw) == 11:
                    cpf = f"{cpf_raw[:3]}.{cpf_raw[3:6]}.{cpf_raw[6:9]}-{cpf_raw[9:]}"
                else:
                    cpf = m.group(2).strip()
                return nome, cpf

    # Padrão 2 – busca CPF isolado próximo de qualquer variação de CONTRATADO
    m = re.search(
        r"CONTRATADO[\s\S]{0,200}?CPF[:\s]*([\d]{3}[\. ]?[\d]{3}[\. ]?[\d]{3}[-\. ]?[\d]{2})",
        texto, re.IGNORECASE
    )
    if m:
        cpf_raw = re.sub(r"[^\d]", "", m.group(1))
        if len(cpf_raw) == 11:
            cpf = f"{cpf_raw[:3]}.{cpf_raw[3:6]}.{cpf_raw[6:9]}-{cpf_raw[9:]}"
        else:
            cpf = m.group(1).strip()

    return nome, cpf


def _extrair_representante_legal(texto: str) -> tuple[str, str]:
    """Mantida para compatibilidade – agora delega para _extrair_representante_tecnico."""
    return _extrair_representante_tecnico(texto)


def _extrair_servicos_anexo1(texto: str) -> list[dict]:
    """
    Extrai os serviços contratados do quadro presente no Anexo 1 (item 1.2 ou 1.3).

    Formato da tabela neste contrato (pdfplumber extrai como texto corrido):
        EXAME Setor de Trabalho Horário Dias da Semana Média de exames e laudos / mês
        Prazo de entrega do laudo Equipamentos
        MAPA Ambulatório Das 07:00 às 19:00 hrs Segunda à sexta 120 5 dias úteis Contratada
        HOLTER Ambulatório ... 120 5 dias úteis Contratada
        Eletrocardiograma Ambulatório ... De acordo com demanda ... 5 dias úteis Contratante

    Retorna lista de dicts com: exame, media_mensal, prazo_entrega.
    """
    servicos = []

    # Localiza o bloco do item 1.2 ou 1.3 até o próximo item numerado
    bloco = ""
    m = re.search(
        r"1\.[23]\s+Os\s+servi[çc]os\s+ser[ãa]o.+?(?=\n\s*1\.[4-9]|\n\s*2\.)",
        texto, re.DOTALL | re.IGNORECASE
    )
    if m:
        bloco = m.group(0)
    else:
        # fallback: captura linhas com MAPA/HOLTER/Eletrocardiograma
        bloco = texto

    # Padrão de cada linha de exame:
    # NOME_EXAME ... <número ou texto de qtd> ... <prazo: N dias úteis>
    # Tenta capturar: nome | media | prazo
    padrao = re.compile(
        r"(MAPA|HOLTER|Eletrocardiograma)"
        r"[\s\S]{0,150}?"
        r"(\d+|De\s+acordo\s+com\s+demanda\s+da\s+unidade[\s\S]{0,60}?(?=\d\s+dias|5\s+dias))"
        r"[\s\S]{0,30}?"
        r"(\d+\s+dias\s+[úu]teis)",
        re.IGNORECASE
    )

    for m in padrao.finditer(bloco):
        exame = m.group(1).strip()
        media_raw = _limpar(m.group(2))
        prazo = _limpar(m.group(3))

        # Normaliza a média: se for texto 'De acordo...', extrai a quantidade entre parênteses
        if re.match(r'^\d+$', media_raw):
            media = media_raw
        else:
            # Pode ter qtd entre parênteses: 'qtd. média de exames) 5'
            qtd_m = re.search(r'\(qtd\.?\s*m[ée]dia\s+de\s+exames\)', media_raw, re.IGNORECASE)
            media = "De acordo com demanda" if qtd_m else _limpar(media_raw)

        servicos.append({
            "exame": exame,
            "media_mensal": media,
            "prazo_entrega": prazo,
        })

    return servicos


def _extrair_servicos(texto: str) -> list[dict]:
    """
    Extrai serviços com valores financeiros da cláusula 3.1.
    Mantido para compatibilidade com a tabela de preços (campo 'servicos' legado).
    """
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
            r"([A-Za-záàãâéêíóôõúç][\w\s]{2,40})\s+(\d+)\s+([\d\.]+,\d{2})\s+([\d\.]+,\d{2})",
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
            r"S[ãa]o\s+Paulo,\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})",
            texto, re.IGNORECASE
        )
        if m:
            data_inicio = _parse_data_pt(m.group(1))

    if data_inicio and meses:
        data_fim = data_inicio + relativedelta(months=meses)

    return data_inicio, data_fim, meses


def _extrair_especialidade(texto: str) -> str:
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
            return esp.replace("Pediatrica", "Pediátrica")
    return ""


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def extrair_contrato(caminho_pdf) -> dict:
    resultado = {
        "razao_social": "",
        "cnpj": "",
        "inscricao_municipal": "",
        "logradouro": "",
        "numero": "",
        "complemento": "",
        "bairro": "",
        "cep": "",
        "cidade": "",
        "objeto": "",
        "servicos": [],             # tabela preços (cláusula 3.1)
        "servicos_contratados": [], # tabela do Anexo 1 (exame, média, prazo)
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
        # Localiza o Anexo 1 para extrações principais
        texto_anexo1 = _localizar_anexo1(texto)

        resultado["numero_processo"] = _extrair_numero_processo(texto)

        # Razão social e CNPJ: usa texto completo (aparecem no Termo de Adesão)
        resultado["razao_social"] = _extrair_razao_social(texto)
        resultado["cnpj"] = _extrair_cnpj(texto)
        resultado["inscricao_municipal"] = _extrair_inscricao_municipal(texto)

        # Endereço: extraído do Termo de Adesão
        end = _extrair_endereco(texto)
        resultado["logradouro"] = end["logradouro"]
        resultado["numero"] = end["numero"]
        resultado["complemento"] = end["complemento"]
        resultado["bairro"] = end["bairro"]
        resultado["cep"] = end["cep"]
        resultado["cidade"] = end["cidade"]

        # Objeto e serviços: usa o Anexo 1
        resultado["objeto"] = _extrair_objeto(texto_anexo1)
        resultado["servicos_contratados"] = _extrair_servicos_anexo1(texto_anexo1)
        resultado["servicos"] = _extrair_servicos(texto)
        resultado["especialidade"] = _extrair_especialidade(texto)
        resultado["valor_mensal"] = _extrair_valor_mensal(texto)
        resultado["valor_global"] = _extrair_valor_global(texto)

        # Representante técnico
        nome_rep, cpf_rep = _extrair_representante_tecnico(texto)
        resultado["nome_representante"] = nome_rep
        resultado["cpf_representante"] = cpf_rep

        data_inicio, data_fim, meses = _extrair_vigencia(texto_anexo1)
        resultado["data_assinatura"] = data_inicio
        resultado["data_fim"] = data_fim
        resultado["meses_vigencia"] = meses

    except Exception as e:
        resultado["erro"] = f"Erro durante extração: {e}"

    return resultado
