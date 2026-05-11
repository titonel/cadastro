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

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


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
# Extração via PyMuPDF (widgets DocuSign)
# ---------------------------------------------------------------------------

def _extrair_widgets_docusign(caminho_pdf) -> dict:
    """
    Usa PyMuPDF para ler os campos de formulário preenchidos pelo DocuSign.
    Retorna dicionário com:
      - 'nome_contratado': nome do signatário CONTRATADO(A)
      - 'cpf_contratado': CPF do signatário (se disponível)

    O widget do CONTRATADO(A) está posicionado logo abaixo do texto
    "CONTRATADO (A)" na página 1 do Termo de Adesão.
    """
    resultado = {"nome_contratado": "", "cpf_contratado": ""}
    if not HAS_PYMUPDF:
        return resultado

    try:
        doc = fitz.open(str(caminho_pdf))
        page = doc[0]  # Termo de Adesão está na página 1

        # Posição Y do texto "CONTRATADO (A)" na página
        y_contratado = None
        for b in page.get_text("dict")["blocks"]:
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    if re.search(r"CONTRATADO\s*\(A\)", span["text"], re.IGNORECASE):
                        y_contratado = span["bbox"][3]  # borda inferior do texto
                        break

        # Coleta todos os widgets FullName com seus valores e posições
        fullnames = []
        for w in page.widgets():
            if "FullName" in w.field_name and w.field_value:
                val = w.field_value.strip()
                # Descarta valores que são UUIDs (campo de sistema)
                if not re.match(r"^[0-9a-f\-]{30,}$", val, re.IGNORECASE):
                    fullnames.append((w.rect.y0, val))

        if fullnames:
            fullnames.sort(key=lambda x: x[0])  # ordena por posição Y

            if y_contratado is not None:
                # Pega o primeiro FullName abaixo de "CONTRATADO (A)"
                for y, val in fullnames:
                    if y >= y_contratado:
                        resultado["nome_contratado"] = val
                        break
            else:
                # Fallback: primeiro nome que não seja do SECONCI/instituição
                resultado["nome_contratado"] = fullnames[0][1]

        doc.close()
    except Exception:
        pass

    return resultado


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
        r"CNPJ\s*(?:n[°º\.]+|sob\s+o\s+n[°º\.]+)?\s*[:\s]*([\d]{2}[\.\/\ ]?[\d]{3}[\.\/\ ]?[\d]{3}[\.\/\ ]?[\d]{4}[-\s]?[\d]{2})",
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
        r"Insc(?:ri[çc][ãa]o)?[\.\ ]?\s+Municipal\s+(?:n[°º.]+)?\s*:?\s*([\d\.\-]+)",
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

    # Captura o trecho entre 'estabelecida na' e 'no município' (ou fallbacks)
    m = re.search(
        r"estabelecida\s+na\s+(.+?)(?:,\s*no\s+munic[íi]pio|Doravante|DECLARA)",
        texto, re.IGNORECASE | re.DOTALL
    )
    if not m:
        # Tenta variação sem vírgula antes de "no município"
        m = re.search(
            r"estabelecida\s+na\s+(.+?)\s+no\s+munic[íi]pio",
            texto, re.IGNORECASE | re.DOTALL
        )
    if not m:
        return resultado

    bloco = _limpar(m.group(1))

    # CEP: '04.141-100' ou '04141-100'
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
    cidade_m = re.search(r"munic[íi]pio\s+de\s+([\w\s]+?)(?:,|$|\n)", texto, re.IGNORECASE)
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
    Extrai nome e CPF do responsável técnico (CONTRATADO(A)).

    Estratégia:
    1. Widgets DocuSign via PyMuPDF — campo FullName posicionado abaixo de
       "CONTRATADO (A)" na página 1 (mais confiável, pois pdfplumber não lê
       os valores dos campos assinados eletronicamente).
    2. Regex sobre o texto extraído por pdfplumber — fallback para contratos
       onde o nome está inserido como texto livre no PDF.
    3. CPF: busca regex após "CONTRATADO" (raramente preenchido via DocuSign).
    """
    nome = ""
    cpf = ""

    # --- Estratégia 1: widgets DocuSign (PyMuPDF) ---
    # Nota: _extrair_widgets_docusign precisa do caminho do arquivo, não do texto.
    # O nome é passado via resultado em extrair_contrato(); aqui a função
    # recebe apenas texto → se já houver nome no texto, usa; senão retorna vazio
    # e extrair_contrato() complementa com os widgets.

    # --- Estratégia 2: regex sobre texto pdfplumber ---
    for pat in [
        r"CONTRATADO\s*\(A\)[\s\S]{0,60}?Nome[:\s]+([^\n\r]{3,80}?)[\s\S]{0,60}?CPF[:\s]+([\d]{3}[\.\ ]?[\d]{3}[\.\ ]?[\d]{3}[-\.\ ]?[\d]{2})",
        r"Contratado\s*\(a\)[\s\S]{0,60}?Nome[:\s]+([^\n\r]{3,80}?)[\s\S]{0,60}?CPF[:\s]+([\d]{3}[\.\ ]?[\d]{3}[\.\ ]?[\d]{3}[-\.\ ]?[\d]{2})",
    ]:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            nome_raw = _limpar(m.group(1))
            cpf_raw = re.sub(r"[^\d]", "", m.group(2))
            # Descarta se capturou número/espaço em branco em vez de nome
            if nome_raw and not re.match(r'^[\d\s\.\-]+$', nome_raw):
                nome = nome_raw
                if len(cpf_raw) == 11:
                    cpf = f"{cpf_raw[:3]}.{cpf_raw[3:6]}.{cpf_raw[6:9]}-{cpf_raw[9:]}"
                else:
                    cpf = m.group(2).strip()
                return nome, cpf

    # --- Estratégia 3: CPF isolado próximo ao bloco CONTRATADO ---
    m = re.search(
        r"CONTRATADO[\s\S]{0,200}?CPF[:\s]*([\d]{3}[\.\ ]?[\d]{3}[\.\ ]?[\d]{3}[-\.\ ]?[\d]{2})",
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
    """Mantida para compatibilidade – delega para _extrair_representante_tecnico."""
    return _extrair_representante_tecnico(texto)


def _extrair_servicos_tabela31(texto: str) -> list[dict]:
    """
    Extrai a tabela financeira da cláusula 3.1 (Descrição, Média, Valor Unit., Valor Total).

    O pdfplumber fragmenta a tabela em colunas intercaladas. O padrão gerado é:
        MAPA 120 4.080,00
        Das Segun 34,00          ← valor unitário aparece no final desta linha
        Ambulatório 07:00 às da à 5 dias úteis
        HOLTER 120 4.680,00
        19:00 hrs sexta 39,00   ← idem
        Eletrocardiograma 50 4,30 215,00   ← 3 valores na mesma linha

    Estratégia:
    - Linha com exame conhecido + 1 valor  → nome, média, total (unit vem na linha seguinte)
    - Linha com exame conhecido + 2 valores → nome, média, unit, total (Eletrocardiograma)
    """
    servicos = []

    # Localiza o bloco da tabela (entre "tabela abaixo" e "Valor Estimado Mensal")
    m_bloco = re.search(
        r"tabela\s+abaixo[:\s]*(.+?)(?:Valor\s+[Ee]stimado\s+[Mm]ensal|3\.2)",
        texto, re.IGNORECASE | re.DOTALL
    )
    if not m_bloco:
        return servicos

    bloco = m_bloco.group(1)
    linhas = bloco.split("\n")

    # Padrão para início de linha de exame: NOME MÉDIA VALOR [VALOR_OPCIONAL]
    pat_exame = re.compile(
        r"^(MAPA|HOLTER|Eletrocardiograma|Eletrocardiogram|ECG)\s+"
        r"(\d+)\s+"
        r"([\d\.]+,\d{2})"          # 1º valor numérico
        r"(?:\s+([\d\.]+,\d{2}))?", # 2º valor (opcional)
        re.IGNORECASE
    )
    # Padrão para capturar valor no final de uma linha de texto misto
    pat_val_final = re.compile(r"([\d\.]+,\d{2})\s*$")

    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        m = pat_exame.match(linha)
        if m:
            nome = m.group(1).strip().title()
            # Normaliza capitalização conhecida
            nome = re.sub(r"^Eletrocardiogram[a]?$", "Eletrocardiograma", nome, flags=re.IGNORECASE)
            media = m.group(2)
            val1 = m.group(3)
            val2 = m.group(4)  # None para MAPA/HOLTER

            prazo = "5 dias úteis"
            # Busca prazo nas próximas linhas
            for j in range(i + 1, min(i + 5, len(linhas))):
                pm = re.search(r"(\d+\s*dias?\s*[úu]teis?)", linhas[j], re.IGNORECASE)
                if pm:
                    prazo = _limpar(pm.group(1))
                    break

            if val2:
                # 3 valores na linha: NOME MEDIA UNIT TOTAL (ex.: Eletrocardiograma)
                unit = val1
                total = val2
            else:
                # 2 valores na linha: NOME MEDIA TOTAL
                # Valor unitário está no final da linha seguinte (texto misto)
                total = val1
                unit = ""
                if i + 1 < len(linhas):
                    mu = pat_val_final.search(linhas[i + 1].strip())
                    if mu:
                        unit = mu.group(1)

            servicos.append({
                "descricao": nome,
                "unidade": nome,
                "quantidade": int(media),
                "media_mensal": media,
                "valor_unitario": float(unit.replace(".", "").replace(",", ".")) if unit else 0.0,
                "valor_total": float(total.replace(".", "").replace(",", ".")),
                "prazo_laudo": prazo,
            })
        i += 1

    return servicos


def _extrair_servicos_anexo1(texto: str) -> list[dict]:
    """
    Extrai os serviços contratados do quadro presente no Anexo 1 (item 1.2 ou 1.3).
    Retorna lista de dicts com: exame, media_mensal, prazo_entrega.
    """
    servicos = []

    bloco = ""
    m = re.search(
        r"1\.[23]\s+Os\s+servi[çc]os\s+ser[ãa]o.+?(?=\n\s*1\.[4-9]|\n\s*2\.)",
        texto, re.DOTALL | re.IGNORECASE
    )
    if m:
        bloco = m.group(0)
    else:
        bloco = texto

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

        if re.match(r'^\d+$', media_raw):
            media = media_raw
        else:
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
    Mantido para compatibilidade. Agora delega para _extrair_servicos_tabela31,
    que lida corretamente com o layout fragmentado do pdfplumber.
    """
    return _extrair_servicos_tabela31(texto)


def _extrair_valor_mensal(texto: str) -> float:
    m = re.search(
        r"valor\s+(?:estimado\s+)?mensal\s+(?:estimado\s+)?(?:de\s+)?R\$\s*([\d\.]+,[\d]{2})",
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
        r"a\s+partir\s+de\s+(.{5,30}?)(?:,|\.|\\n|correspondente)",
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
        "servicos": [],              # tabela financeira 3.1 (compatibilidade)
        "servicos_contratados": [],  # tabela do Anexo 1 (exame, média, prazo)
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
        texto_anexo1 = _localizar_anexo1(texto)

        resultado["numero_processo"] = _extrair_numero_processo(texto)
        resultado["razao_social"] = _extrair_razao_social(texto)
        resultado["cnpj"] = _extrair_cnpj(texto)
        resultado["inscricao_municipal"] = _extrair_inscricao_municipal(texto)

        # Endereço: extraído do Termo de Adesão (texto completo)
        end = _extrair_endereco(texto)
        resultado["logradouro"] = end["logradouro"]
        resultado["numero"] = end["numero"]
        resultado["complemento"] = end["complemento"]
        resultado["bairro"] = end["bairro"]
        resultado["cep"] = end["cep"]
        resultado["cidade"] = end["cidade"]

        resultado["objeto"] = _extrair_objeto(texto_anexo1)
        resultado["especialidade"] = _extrair_especialidade(texto)
        resultado["valor_mensal"] = _extrair_valor_mensal(texto)
        resultado["valor_global"] = _extrair_valor_global(texto)

        # Tabela financeira 3.1 – MAPA, HOLTER, Eletrocardiograma com valores
        resultado["servicos"] = _extrair_servicos_tabela31(texto)

        # Tabela do Anexo 1 – exame, média, prazo (sem valores financeiros)
        resultado["servicos_contratados"] = _extrair_servicos_anexo1(texto_anexo1)

        # Representante técnico
        # Prioridade 1: widgets DocuSign (PyMuPDF) – campo preenchido eletronicamente
        widgets = _extrair_widgets_docusign(caminho_pdf)
        nome_rep = widgets.get("nome_contratado", "")
        cpf_rep = widgets.get("cpf_contratado", "")

        # Prioridade 2: fallback por regex sobre texto pdfplumber
        if not nome_rep:
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
