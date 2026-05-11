"""
extrator.py – Extrai dados estruturados de contratos PDF do padrão SECONCI/AME.

Versão 3 – correções:
  - Endereço: separa corretamente logradouro, número e bairro quando o padrão
    é "LOGRADOURO, NÚMERO, BAIRRO, CEP: XXXXX" (vírgulas como separador).
  - Representante: rejeita resultado do DocuSign quando contém apenas uma palavra
    (ex: "Tatiana" em vez de "Tatiana Rozov") e usa o fallback regex do pdfplumber.
  - Tabela Anexo 1 Formato B: estratégia reescrita para capturar linhas da tabela
    1.3 mesmo quando o pdfplumber as fragmenta em múltiplas linhas.
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


def _title_case_nome(nome: str) -> str:
    """
    Converte 'FERNANDO ANTONIO AQUINO GONDIM' -> 'Fernando Antonio Aquino Gondim'.
    Mantém partículas (de, da, dos, e) em minúsculo.
    """
    particulas = {"de", "da", "do", "das", "dos", "e", "em", "ou"}
    partes = nome.strip().split()
    resultado = []
    for i, p in enumerate(partes):
        if i > 0 and p.lower() in particulas:
            resultado.append(p.lower())
        else:
            resultado.append(p.capitalize())
    return " ".join(resultado)


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
    m = re.search(r"ANEXO\s+[I1]\b|ANEXO\s+III\s*[:\-]?\s*CONTRATO", texto, re.IGNORECASE)
    if m:
        return texto[m.start():]
    return texto


# ---------------------------------------------------------------------------
# Extratores via PyMuPDF (widgets DocuSign + texto de páginas específicas)
# ---------------------------------------------------------------------------

def _extrair_widgets_docusign(caminho_pdf) -> dict:
    """
    Usa PyMuPDF para:
    1. Ler campos de formulário FullName preenchidos pelo DocuSign (nome contratado).
    2. Ler o texto da última página do documento assinado para capturar:
       - Nome e CPF do CONTRATADO(A) (bloco de assinatura)
       - Nome e CPF da Testemunha Contratado(A)
    """
    resultado = {
        "nome_contratado": "",
        "cpf_contratado": "",
        "nome_testemunha": "",
        "cpf_testemunha": "",
    }
    if not HAS_PYMUPDF:
        return resultado

    try:
        doc = fitz.open(str(caminho_pdf))

        # -----------------------------------------------------------------
        # Estratégia 1: widgets FullName na página 1 (Termo de Adesão)
        # Rejeita nomes com apenas UMA palavra (ex: "Tatiana" em vez de
        # "Tatiana Rozov") — são assinaturas desenhadas/abreviadas do DocuSign.
        # -----------------------------------------------------------------
        page0 = doc[0]
        y_contratado = None
        for b in page0.get_text("dict")["blocks"]:
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    if re.search(r"CONTRATADO\s*\(A\)", span["text"], re.IGNORECASE):
                        y_contratado = span["bbox"][3]
                        break

        fullnames = []
        for w in page0.widgets():
            if "FullName" in (w.field_name or "") and w.field_value:
                val = w.field_value.strip()
                if not re.match(r"^[0-9a-f\-]{30,}$", val, re.IGNORECASE):
                    fullnames.append((w.rect.y0, val))

        if fullnames:
            fullnames.sort(key=lambda x: x[0])
            if y_contratado is not None:
                for y, val in fullnames:
                    if y >= y_contratado:
                        # Só aceita se tiver pelo menos 2 palavras (nome completo)
                        if len(val.split()) >= 2:
                            resultado["nome_contratado"] = _title_case_nome(val)
                        break
            else:
                val = fullnames[0][1]
                if len(val.split()) >= 2:
                    resultado["nome_contratado"] = _title_case_nome(val)

        # -----------------------------------------------------------------
        # Estratégia 2: varrer TODAS as páginas buscando bloco de assinatura
        # com 'CONTRATADO (A)' / 'Testemunha Contratado'
        # -----------------------------------------------------------------
        texto_completo_doc = []
        for pg in doc:
            t = pg.get_text()
            if t:
                texto_completo_doc.append(t)
        texto_todas = "\n".join(texto_completo_doc)

        # Nome e CPF do CONTRATADO(A) a partir do bloco de assinatura textual
        if not resultado["nome_contratado"]:
            m_cont = re.search(
                r"CONTRATADO\s*\(A\)[\s\S]{0,80}?"
                r"Nome\s*:\s*([^\n\r]+?)[\s\S]{0,40}?"
                r"CPF\s*:\s*([\d\s\.\-]{9,14})",
                texto_todas, re.IGNORECASE
            )
            if m_cont:
                nome_raw = _limpar(m_cont.group(1))
                if nome_raw and not re.match(r"^[\d\s\.\-]+$", nome_raw):
                    resultado["nome_contratado"] = _title_case_nome(nome_raw)
                cpf_raw = re.sub(r"[^\d]", "", m_cont.group(2))
                if len(cpf_raw) == 11:
                    resultado["cpf_contratado"] = f"{cpf_raw[:3]}.{cpf_raw[3:6]}.{cpf_raw[6:9]}-{cpf_raw[9:]}"

        # CPF do contratado (mesmo que o nome já tenha sido capturado)
        if not resultado["cpf_contratado"]:
            m_cpf = re.search(
                r"CONTRATADO\s*\(A\)[\s\S]{0,120}?CPF\s*:\s*([\d\s\.\-]{9,14})",
                texto_todas, re.IGNORECASE
            )
            if m_cpf:
                cpf_raw = re.sub(r"[^\d]", "", m_cpf.group(1))
                if len(cpf_raw) == 11:
                    resultado["cpf_contratado"] = f"{cpf_raw[:3]}.{cpf_raw[3:6]}.{cpf_raw[6:9]}-{cpf_raw[9:]}"

        # -----------------------------------------------------------------
        # Estratégia 3: testemunha do contratado
        # -----------------------------------------------------------------
        for pg in doc:
            y_test = None
            for b in pg.get_text("dict")["blocks"]:
                for line in b.get("lines", []):
                    for span in line.get("spans", []):
                        txt = span["text"]
                        if re.search(r"Testemunha[\s\S]{0,30}?Contratado", txt, re.IGNORECASE):
                            y_test = span["bbox"][3]
                            break

            if y_test is not None:
                fntest = []
                for w in pg.widgets():
                    if "FullName" in (w.field_name or "") and w.field_value:
                        val = w.field_value.strip()
                        if not re.match(r"^[0-9a-f\-]{30,}$", val, re.IGNORECASE):
                            fntest.append((w.rect.y0, val))
                if fntest:
                    fntest.sort(key=lambda x: x[0])
                    for y, val in fntest:
                        if y >= y_test and val != resultado.get("nome_contratado", ""):
                            resultado["nome_testemunha"] = _title_case_nome(val)
                            break

        # Fallback: regex sobre texto de todas as páginas
        if not resultado["nome_testemunha"]:
            m_test = re.search(
                r"Testemunha[\s\S]{0,30}?Contratado\s*\(A?\)[\s\S]{0,120}?"
                r"Nome\s*:\s*([A-Z][A-Za-z\u00c0-\u00ff\s]{3,60}?)(?:\s*\n|\s*CPF)",
                texto_todas, re.IGNORECASE
            )
            if m_test:
                nome_raw = _limpar(m_test.group(1))
                if len(nome_raw) >= 5 and not re.match(r"^[\d\s\.\-]+$", nome_raw):
                    resultado["nome_testemunha"] = _title_case_nome(nome_raw)

        # CPF da testemunha
        if not resultado.get("cpf_testemunha"):
            m_cpf_t = re.search(
                r"Testemunha[\s\S]{0,30}?Contratado[\s\S]{0,150}?CPF\s*:\s*([\d\s\.\-]{9,14})",
                texto_todas, re.IGNORECASE
            )
            if m_cpf_t:
                cpf_raw = re.sub(r"[^\d]", "", m_cpf_t.group(1))
                if len(cpf_raw) == 11:
                    resultado["cpf_testemunha"] = f"{cpf_raw[:3]}.{cpf_raw[3:6]}.{cpf_raw[6:9]}-{cpf_raw[9:]}"

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
    m = re.search(r"(\d{3,6})\s*[\u2013-]\s*ID[:\s]*(\d+)", texto)
    if m:
        return m.group(1).strip()
    return ""


def _extrair_razao_social(texto: str) -> str:
    """
    Extrai a razão social da contratada.
    Padrão 1: "Pelo presente instrumento, RAZAO SOCIAL, inscrita"
    Padrão 2: "instrumento, RAZAO SOCIAL, inscrita"
    Padrão 3: "AME CARAGUATATUBA e RAZAO SOCIAL, doravante"
    """
    m = re.search(
        r"presente\s+instrumento,\s+([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-ZÁÀÃÂÉÊÍÓÔÕÚÇ\s\-\.]{2,80}?)\s*,\s*inscrit",
        texto, re.IGNORECASE
    )
    if m:
        return _limpar(m.group(1))

    m = re.search(
        r"instrumento,\s+([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-ZÁÀÃÂÉÊÍÓÔÕÚÇ\s\-\.]{2,80}?)\s*,?\s*inscrit",
        texto, re.IGNORECASE
    )
    if m:
        return _limpar(m.group(1))

    m = re.search(
        r"AME\s+CARAGUATATUBA\s+e\s+([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-ZÁÀÃÂÉÊÍÓÔÕÚÇ\s\-\.]{2,80}?)\s*,\s*doravante",
        texto, re.IGNORECASE
    )
    if m:
        return _limpar(m.group(1))

    return ""


def _extrair_cnpj(texto: str) -> str:
    matches = re.findall(
        r"CNPJ\s*(?:n[°º\.]+|sob\s+o\s+n[°º\.]+)?\s*[:\s]*([\d]{2}[\.\/\s]?[\d]{3}[\.\/\s]?[\d]{3}[\.\/\s]?[\d]{4}[-\s]?[\d]{2})",
        texto, re.IGNORECASE
    )
    if matches:
        raw = re.sub(r"\s", "", matches[0])
        if re.match(r"^\d{14}$", raw):
            raw = f"{raw[:2]}.{raw[2:5]}.{raw[5:8]}/{raw[8:12]}-{raw[12:]}"
        return raw
    return ""


def _extrair_inscricao_municipal(texto: str) -> str:
    m = re.search(
        r"Inscri[\u00e7c][\u00e3a]o\s+Municipal\s+[Ss]ob\s+N[.\u00ba\u00b0]+\s*([\d\.\-]+)",
        texto, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()
    m = re.search(
        r"Inscri[\u00e7c][\u00e3a]o\s+Municipal\s+(?:n[°º.]+\s*)?:?\s*([\d\.\-]+)",
        texto, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()
    return ""


def _extrair_endereco(texto: str) -> dict:
    """
    Extrai endereço a partir de padrões como:
      "com sede na LOGRADOURO, NUMERO, BAIRRO, CEP: XXXXX"
      "estabelecida na LOGRADOURO, NUMERO - COMPLEMENTO, CEP XXXXX"

    Separação:
      - O campo imediatamente após a vírgula do logradouro que começa com dígito
        é o NÚMERO.
      - O campo seguinte (antes do CEP) é o BAIRRO (podendo conter " - complemento").
    """
    resultado = {
        "logradouro": "",
        "numero": "",
        "complemento": "",
        "bairro": "",
        "cep": "",
        "cidade": "",
    }

    bloco = ""
    for prefixo in [
        r"estabelecida\s+na\s+",
        r"com\s+sede\s+na\s+",
        r"sede\s+(?:social\s+)?na\s+",
    ]:
        m = re.search(
            prefixo + r"(.+?)(?:,?\s*no\s+munic[íi]pio|Doravante|DECLARA)",
            texto, re.IGNORECASE | re.DOTALL
        )
        if m:
            bloco = _limpar(m.group(1))
            break

    if not bloco:
        return resultado

    # ── Extrai CEP e remove do bloco ──────────────────────────────────────
    cep_m = re.search(r"CEP[:\s]+([\d]{2}\.?[\d]{3}[-–][\d]{3})", bloco, re.IGNORECASE)
    if not cep_m:
        cep_m = re.search(r"([\d]{5}[-–][\d]{3})", bloco)
    if cep_m:
        resultado["cep"] = cep_m.group(1).strip()
        bloco = bloco[:cep_m.start()].strip().rstrip(",").strip()

    # ── Extrai cidade ──────────────────────────────────────────────────────
    cidade_m = re.search(r"munic[íi]pio\s+de\s+([\w\s]+?)(?:,|$|\n)", texto, re.IGNORECASE)
    if cidade_m:
        resultado["cidade"] = _limpar(cidade_m.group(1))

    # ── Decompõe: LOGRADOURO, NUMERO, BAIRRO [- COMPLEMENTO] ──────────────
    # Divide por vírgula
    partes = [p.strip() for p in bloco.split(",")]

    if len(partes) >= 3:
        # Padrão "LOGRADOURO, NUMERO, BAIRRO" (3 ou mais segmentos)
        resultado["logradouro"] = partes[0]

        # Segundo segmento deve iniciar com dígito (número)
        if re.match(r"^\d+", partes[1]):
            resultado["numero"] = partes[1]
        else:
            # Número pode estar embutido no final do logradouro (ex: "RUA X 123")
            num_emb = re.search(r"\b(\d+)\s*$", partes[0])
            if num_emb:
                resultado["logradouro"] = partes[0][:num_emb.start()].strip()
                resultado["numero"] = num_emb.group(1)
            else:
                resultado["numero"] = partes[1]

        # Restante (parte[2] em diante) é bairro + possível complemento
        bairro_raw = ", ".join(partes[2:]).strip()
        # Separa complemento se houver " - "
        if " - " in bairro_raw:
            bairro_split = bairro_raw.split(" - ", 1)
            resultado["bairro"] = bairro_split[0].strip()
            resultado["complemento"] = bairro_split[1].strip()
        else:
            resultado["bairro"] = bairro_raw

    elif len(partes) == 2:
        resultado["logradouro"] = partes[0]
        # Tenta separar número do bairro dentro da segunda parte
        m2 = re.match(r"^(\d+)\s*(.*)", partes[1])
        if m2:
            resultado["numero"] = m2.group(1)
            resultado["bairro"] = m2.group(2).strip()
        else:
            resultado["logradouro"] = partes[1]

    else:
        # Apenas uma parte: tenta extrair número via regex
        m3 = re.match(r"^(.+?),?\s*(\d+)\s*(.*)", bloco)
        if m3:
            resultado["logradouro"] = m3.group(1).strip()
            resultado["numero"] = m3.group(2)
            resultado["bairro"] = m3.group(3).strip()
        else:
            resultado["logradouro"] = bloco

    return resultado


def _extrair_objeto(texto: str) -> str:
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
        return _limpar(bloco_11.replace("1.1", "").replace("1.2", ""))[:300].rstrip(".")

    return ""


def _extrair_representante_tecnico(texto: str) -> tuple[str, str]:
    """
    Extrai nome e CPF do CONTRATADO(A) por regex no texto pdfplumber.
    Usado como fallback quando PyMuPDF não consegue (ou retorna nome incompleto).

    Padrão esperado no PDF:
        CONTRATADO (A)
        Nome: Tatiana Rozov
        CPF: 03954978849
    """
    # Padrão principal: "CONTRATADO (A) ... Nome: NOME ... CPF: NUMERO"
    for pat in [
        r"CONTRATADO\s*\(A\)[\s\S]{0,80}?Nome\s*:\s*([^\n\r]{3,80}?)[\s\S]{0,60}?CPF\s*:\s*([\d]{3}[\.\s]?[\d]{3}[\.\s]?[\d]{3}[-\.\s]?[\d]{2})",
        r"Contratado\s*\(a\)[\s\S]{0,80}?Nome\s*:\s*([^\n\r]{3,80}?)[\s\S]{0,60}?CPF\s*:\s*([\d]{3}[\.\s]?[\d]{3}[\.\s]?[\d]{3}[-\.\s]?[\d]{2})",
    ]:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            nome_raw = _limpar(m.group(1))
            cpf_raw = re.sub(r"[^\d]", "", m.group(2))
            if nome_raw and not re.match(r'^[\d\s\.\-]+$', nome_raw):
                nome = _title_case_nome(nome_raw)
                cpf = f"{cpf_raw[:3]}.{cpf_raw[3:6]}.{cpf_raw[6:9]}-{cpf_raw[9:]}" if len(cpf_raw) == 11 else m.group(2).strip()
                return nome, cpf

    # Fallback: só CPF
    m = re.search(
        r"CONTRATADO[\s\S]{0,200}?CPF[:\s]*([\d]{3}[\.\s]?[\d]{3}[\.\s]?[\d]{3}[-\.\s]?[\d]{2})",
        texto, re.IGNORECASE
    )
    if m:
        cpf_raw = re.sub(r"[^\d]", "", m.group(1))
        cpf = f"{cpf_raw[:3]}.{cpf_raw[3:6]}.{cpf_raw[6:9]}-{cpf_raw[9:]}" if len(cpf_raw) == 11 else m.group(1).strip()
        return "", cpf

    return "", ""


def _extrair_representante_legal(texto: str) -> tuple[str, str]:
    """Alias de compatibilidade."""
    return _extrair_representante_tecnico(texto)


# ---------------------------------------------------------------------------
# Extratores de serviços
# ---------------------------------------------------------------------------

def _detectar_formato_tabela(bloco: str) -> str:
    """
    Detecta o formato da tabela de serviços.
    Retorna 'A' (MAPA/HOLTER/ECG) ou 'B' (Especialidade+Serviço genérico).
    """
    if re.search(r"\b(MAPA|HOLTER|Eletrocardiograma)\b", bloco, re.IGNORECASE):
        return "A"
    if re.search(r"\b(Consultas?\s+Ambulatoriais?|Prova\s+de\s+fun[\u00e7c][\u00e3a]o)", bloco, re.IGNORECASE):
        return "B"
    return "B"  # default


def _extrair_servicos_formato_a(bloco: str) -> list[dict]:
    """
    Formato A: tabela do contrato de MAPA/HOLTER/ECG.
    Colunas relevantes: Descrição | Média | Prazo | Valor Unit. | Valor Total.
    """
    servicos = []
    linhas = bloco.split("\n")

    pat_exame = re.compile(
        r"^(MAPA|HOLTER|Eletrocardiograma|Eletrocardiogram|ECG)\s+"
        r"(\d+)\s+"
        r"([\d\.]+,\d{2})"
        r"(?:\s+([\d\.]+,\d{2}))?",
        re.IGNORECASE
    )
    pat_val_final = re.compile(r"([\d\.]+,\d{2})\s*$")

    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        m = pat_exame.match(linha)
        if m:
            nome = m.group(1).strip().title()
            nome = re.sub(r"^Eletrocardiogram[a]?$", "Eletrocardiograma", nome, flags=re.IGNORECASE)
            media = m.group(2)
            val1 = m.group(3)
            val2 = m.group(4)

            prazo = "5 dias úteis"
            for j in range(i + 1, min(i + 5, len(linhas))):
                pm = re.search(r"(\d+\s*dias?\s*[\u00fau]teis?)", linhas[j], re.IGNORECASE)
                if pm:
                    prazo = _limpar(pm.group(1))
                    break

            if val2:
                unit, total = val1, val2
            else:
                total = val1
                unit = ""
                if i + 1 < len(linhas):
                    mu = pat_val_final.search(linhas[i + 1].strip())
                    if mu:
                        unit = mu.group(1)

            servicos.append({
                "descricao": nome,
                "tipo_servico": "exame",
                "unidade_medida": "Laudo",
                "quantidade_estimada_mes": int(media),
                "media_mensal": media,
                "valor_unitario": float(unit.replace(".", "").replace(",", ".")) if unit else 0.0,
                "valor_total": float(total.replace(".", "").replace(",", ".")),
                "prazo_entrega_laudo_dias": int(re.search(r"\d+", prazo).group()) if re.search(r"\d+", prazo) else None,
            })
        i += 1

    return servicos


def _extrair_servicos_formato_b(bloco: str) -> list[dict]:
    """
    Formato B: tabela genérica com colunas
    Especialidade | Serviço | Setor | Dias | Horários | Nº Prof. | Qtde. | Unid.Med. | Valor Unit. | Valor Total
    """
    servicos = []
    linhas = [l.strip() for l in bloco.split("\n") if l.strip()]

    # Padrão: linha contendo Qtde Unidade ValorUnit ValorTotal
    pat_linha_valor = re.compile(
        r"^(\d+)\s+"
        r"([A-Za-z\u00c0-\u00ff][\w\s\u00c0-\u00ff]{0,30})\s+"
        r"([\d\.]+,\d{2})\s+"
        r"([\d\.]+,\d{2})$"
    )

    pat_nome_servico = re.compile(
        r"(Consultas?\s+Ambulatoriais?|Prova\s+de\s+fun[\u00e7c][\u00e3a]o\s+pulmonar|SADT|Laudos?|Procedimentos?|[A-Z][\w\s]{3,40})",
        re.IGNORECASE
    )

    for i, linha in enumerate(linhas):
        m = pat_linha_valor.match(linha)
        if m:
            qtde = int(m.group(1))
            unid = _limpar(m.group(2))
            unit_str = m.group(3)
            total_str = m.group(4)

            nome_servico = ""
            for k in range(max(0, i - 5), i):
                mn = pat_nome_servico.search(linhas[k])
                if mn:
                    cand = _limpar(mn.group(1))
                    if cand.lower() not in {"especialidade", "serviço", "setor", "qtde", "unid", "valor"}:
                        if len(cand) > 4:
                            nome_servico = cand

            tipo = "consulta" if re.search(r"consult", unid, re.IGNORECASE) else "exame"

            servicos.append({
                "descricao": nome_servico or f"Serviço {unid}",
                "tipo_servico": tipo,
                "unidade_medida": unid,
                "quantidade_estimada_mes": qtde,
                "media_mensal": str(qtde),
                "valor_unitario": float(unit_str.replace(".", "").replace(",", ".")),
                "valor_total": float(total_str.replace(".", "").replace(",", ".")),
                "prazo_entrega_laudo_dias": None,
            })

    return servicos


def _extrair_servicos_tabela31(texto: str) -> list[dict]:
    """
    Ponto de entrada unificado: localiza o bloco da tabela 3.1,
    detecta o formato e delega para o extrator correto.
    """
    m_bloco = re.search(
        r"tabela\s+abaixo[:\s]*(.+?)(?:Valor\s+[Ee]stimado\s+[Mm]ensal|3\.2)",
        texto, re.IGNORECASE | re.DOTALL
    )
    if not m_bloco:
        m_bloco = re.search(
            r"3\.1[\s\S]{0,100}?pagará[\s\S]{0,50}?tabela[\s\S]{0,20}?"
            r"(.+?)(?:Valor\s+[Ee]stimado|3\.2)",
            texto, re.IGNORECASE | re.DOTALL
        )
    if not m_bloco:
        return []

    bloco = m_bloco.group(1)
    formato = _detectar_formato_tabela(bloco)

    if formato == "A":
        return _extrair_servicos_formato_a(bloco)
    else:
        return _extrair_servicos_formato_b(bloco)


def _extrair_servicos_anexo1(texto: str) -> list[dict]:
    """
    Extrai os serviços do quadro do Anexo 1 (item 1.2 ou 1.3).

    Formato A (MAPA/HOLTER/ECG): extrai exame, media_mensal, prazo_entrega.
    Formato B (consultas/laudos): varre o bloco da seção 1.3 e captura
        linhas com padrão 'Serviço | ... | Qtde | Unidade' geradas pelo pdfplumber,
        incluindo o padrão de tabela fragmentada em múltiplas linhas.
    """
    servicos = []

    # Localiza o bloco da seção 1.3 (ou 1.2)
    bloco = ""
    for pat_secao in [
        r"1\.3[\s\S]{0,30}?Os\s+servi[\u00e7c]os.+?(?=\n\s*1\.[4-9]|\n\s*2\.|\n\s*V\.)",
        r"1\.2[\s\S]{0,30}?Os\s+servi[\u00e7c]os.+?(?=\n\s*1\.[3-9]|\n\s*2\.|\n\s*V\.)",
        r"1\.[23][\s\S]{0,30}Os\s+servi[\u00e7c]os.+?(?=\n\s*1\.[4-9]|\n\s*2\.|\n\s*V\.)",
    ]:
        m = re.search(pat_secao, texto, re.DOTALL | re.IGNORECASE)
        if m:
            bloco = m.group(0)
            break

    if not bloco:
        bloco = texto

    formato = _detectar_formato_tabela(bloco)

    # ── Formato A: MAPA / HOLTER / ECG ────────────────────────────────────
    if formato == "A":
        padrao = re.compile(
            r"(MAPA|HOLTER|Eletrocardiograma)"
            r"[\s\S]{0,150}?"
            r"(\d+|De\s+acordo\s+com\s+demanda[\s\S]{0,60}?(?=\d\s+dias|5\s+dias))"
            r"[\s\S]{0,30}?"
            r"(\d+\s+dias\s+[\u00fau]teis)",
            re.IGNORECASE
        )
        for m in padrao.finditer(bloco):
            exame = m.group(1).strip()
            media_raw = _limpar(m.group(2))
            prazo = _limpar(m.group(3))
            media = media_raw if re.match(r'^\d+$', media_raw) else "De acordo com demanda"
            servicos.append({"exame": exame, "media_mensal": media, "prazo_entrega": prazo})
        return servicos

    # ── Formato B: consultas / laudos (tabela 1.3 fragmentada) ────────────
    #
    # O pdfplumber pode gerar o conteúdo da tabela como:
    #   a) uma linha por célula ("Consultas Ambulatoriais", "48", "Consulta")
    #   b) múltiplas células na mesma linha ("Pneumologia Pediátrica | Consultas | ... | 48 | Consulta")
    #   c) linha com apenas Qtde + Unidade ("48 Consulta")
    #
    # Estratégia: busca padrões de quantidade + unidade e retroativamente
    # recupera o nome do serviço nas linhas vizinhas.

    linhas = [l.strip() for l in bloco.split("\n") if l.strip()]

    # Nomes de serviços conhecidos
    pat_nome = re.compile(
        r"(Consultas?\s+Ambulatoriais?|Prova\s+de\s+fun[\u00e7c][\u00e3a]o\s+pulmonar"
        r"|SADT[^\n]{0,40}|Laudos?\s+[\w\s]{0,30}|Procedimentos?[\s\w]{0,30})",
        re.IGNORECASE
    )

    # Padrão de linha "QTDE UNIDADE" (sem valores monetários – esses ficam na seção 3.1)
    pat_qtde_unid = re.compile(
        r"^(\d{1,4})\s+"
        r"(Consulta|Laudo|Atendimento|Procedimento|[\w]+)"
        r"\s*$",
        re.IGNORECASE
    )

    # Padrão alternativo: linha que termina com "| QTDE | UNIDADE"
    # Ex: "Pneumologia Pediátrica | Consultas | Ambulatório | ... | 48 | Consulta"
    pat_linha_tabela = re.compile(
        r"(\d{1,4})\s+(Consulta|Laudo|Atendimento|Procedimento|[\w]+)\s*$",
        re.IGNORECASE
    )

    # Prazo (busca no bloco inteiro da seção)
    prazo_m = re.search(
        r"(\d+\s*\([\w\s]+\)\s*dias?\s*[\u00fau]teis?|\d+\s+dias?\s+[\u00fau]teis?)",
        bloco, re.IGNORECASE
    )
    prazo_global = _limpar(prazo_m.group(1)) if prazo_m else ""

    # Varredura das linhas
    vistos = set()
    for i, linha in enumerate(linhas):
        # Tenta o padrão estrito (só qtde + unidade)
        m_q = pat_qtde_unid.match(linha)
        if not m_q:
            # Tenta o padrão "qualquer linha que termine com qtde + unidade"
            m_q = pat_linha_tabela.search(linha)

        if m_q:
            qtde = m_q.group(1)
            unid = _limpar(m_q.group(2))

            # Evita duplicatas
            chave = f"{qtde}_{unid}"
            if chave in vistos:
                continue
            vistos.add(chave)

            # Busca nome do serviço nas 8 linhas anteriores
            nome_servico = ""
            for k in range(max(0, i - 8), i + 1):
                mn = pat_nome.search(linhas[k])
                if mn:
                    cand = _limpar(mn.group(1))
                    if cand.lower() not in {"especialidade", "serviço", "setor", "qtde", "unid", "valor"}:
                        if len(cand) > 4:
                            nome_servico = cand

            if nome_servico or unid.lower() not in {"especialidade", "serviço", "setor"}:
                servicos.append({
                    "exame": nome_servico or unid,
                    "media_mensal": qtde,
                    "prazo_entrega": prazo_global,
                })

    # Fallback: se não encontrou nada via varredura de linhas,
    # tenta extrair diretamente das linhas que mencionam nome de serviço + número
    if not servicos:
        for m_fn in re.finditer(
            r"(Consultas?\s+Ambulatoriais?|Prova\s+de\s+fun[\u00e7c][\u00e3a]o\s+pulmonar)"
            r"[\s\S]{0,200}?"
            r"(\d{1,4})\s+(Consulta|Laudo)",
            bloco, re.IGNORECASE
        ):
            servicos.append({
                "exame": _limpar(m_fn.group(1)),
                "media_mensal": m_fn.group(2),
                "prazo_entrega": prazo_global,
            })

    return servicos


def _extrair_servicos(texto: str) -> list[dict]:
    """Alias de compatibilidade."""
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
        "nome_testemunha": "",
        "cpf_testemunha": "",
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

        resultado["servicos"] = _extrair_servicos_tabela31(texto)
        resultado["servicos_contratados"] = _extrair_servicos_anexo1(texto_anexo1)

        # Representante técnico + testemunha: PyMuPDF primeiro
        widgets = _extrair_widgets_docusign(caminho_pdf)
        nome_rep = widgets.get("nome_contratado", "")
        cpf_rep = widgets.get("cpf_contratado", "")
        nome_test = widgets.get("nome_testemunha", "")
        cpf_test = widgets.get("cpf_testemunha", "")

        # Fallback regex pdfplumber:
        # Usa quando PyMuPDF não retornou nada OU retornou nome com apenas 1 palavra
        # (widget de assinatura desenhada contém só o primeiro nome / apelido)
        if not nome_rep or len(nome_rep.split()) < 2:
            nome_rep_fb, cpf_rep_fb = _extrair_representante_tecnico(texto)
            if nome_rep_fb:
                nome_rep = nome_rep_fb
            if cpf_rep_fb and not cpf_rep:
                cpf_rep = cpf_rep_fb

        resultado["nome_representante"] = nome_rep
        resultado["cpf_representante"] = cpf_rep
        resultado["nome_testemunha"] = nome_test
        resultado["cpf_testemunha"] = cpf_test

        data_inicio, data_fim, meses = _extrair_vigencia(texto_anexo1)
        resultado["data_assinatura"] = data_inicio
        resultado["data_fim"] = data_fim
        resultado["meses_vigencia"] = meses

    except Exception as e:
        resultado["erro"] = f"Erro durante extração: {e}"

    return resultado
