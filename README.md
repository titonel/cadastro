# Âmbar — Sistema de Gestão

Sistema web Django para gestão integrada de prestadores, contratos e produção ambulatorial do **AME Caraguatatuba** (SECONCI-SP / SUS–OSS).

---

## Visão Geral

O Âmbar centraliza quatro grandes funções de gestão:

| Módulo | Rota | Descrição |
|---|---|---|
| **Acompanhamento** | `/acompanhamento/` | Importação e registro da produção extraída do SIRESP |
| **Relatório** | `/relatorio/` | Geração de relatório de produção em XLSX |
| **Prestadores** | `/prestadores/` | CRUD completo de prestadores e contratos |
| **Contratos** | `/contrato/upload/` | Importação e extração automática de dados de contratos PDF |

---

## Orientações quanto à Identidade Visual

**Nome do projeto:** Âmbar  
**Paleta:** Dia Ensolarado (Figma)

| Token | Hex | Uso |
|---|---|---|
| Âmbar | `#FFBF00` | Cor primária, foco de campos, stripe do card Prestadores |
| Âmbar escuro | `#807040` | Títulos de seção, textos secundários, stripe Relatório |
| Azul | `#007EFF` | Links, mensagens info, stripe Acompanhamento |
| Azul profundo | `#2400FF` | Hover de links, stripe Indicadores |

**Tipografia:** Lato (Google Fonts) — pesos 300, 400, 700, 900, regular e itálico  
**Símbolo:** pedra de âmbar com inclusão, construída em SVG inline (navbar e hero da homepage)

---

## Funcionalidades

### Módulo 1 — Acompanhamento de Produção

Importação de arquivos de produção extraídos diretamente do portal **SIRESP** (Secretaria de Estado da Saúde de São Paulo).

#### Formatos suportados

O SIRESP exporta arquivos com extensão `.xls` que são, na verdade, **documentos HTML em ISO-8859-1** sem assinatura binária OLE2/BIFF. O sistema detecta o formato automaticamente pelo primeiro byte do arquivo:

| Formato | Critério de detecção | Parser utilizado |
|---|---|---|
| HTML disfarçado (SIRESP atual) | `byte[0] == '<'` | `pandas.read_html()` |
| XLS binário legado (BIFF/OLE2) | magic bytes `D0CF11E0...` | `xlrd` |
| XLSX / XLSM (ZIP/OOXML) | demais casos | `openpyxl` |

#### Relatório de Consultas (`producao_siresp.py`)

- Extrai o período do campo de metadados (`Período:DD-MM-AAAAaDD-MM-AAAA`)
- Pula 4 linhas de cabeçalho hierárquico (colspan/rowspan)
- 29 colunas (A–AC): vagas ofertadas, agendamentos (total, bolsão, não distribuídas, cota, extra), recepção (presencial, teleconsulta, ausente, dispensado, desistente, não informado) e altas
- Identifica linhas de **agenda** pelo conjunto `AGENDAS_CONHECIDAS` (59 agendas configuradas)
- Identifica linhas de **profissional** por `str.isupper()` — nomes exclusivamente em maiúsculas
- Armazena separadamente a produção consolidada da agenda (`ProducaoAgenda`) e a produção individual de cada profissional (`ProducaoMedico`); um mesmo profissional pode aparecer em múltiplas agendas

#### Relatório de Cirurgias e Exames (`producao_siresp_exames.py`)

- Mesma lógica de detecção de formato e extração de período
- **3 linhas de cabeçalho** (diferença estrutural em relação ao relatório de Consultas)
- 25 colunas (A–Y): vagas, agendamentos, atendidos, ausentes, dispensados, desistentes, não informados e altas
- Agendas também estão em **maiúsculas** — identificadas pelo conjunto `AGENDAS_SIRESP_EXAMES` (102 agendas configuradas)
- Profissionais identificados por exclusão: strings em maiúsculas que não constam no conjunto de agendas

#### Histórico de importações

- Listagem tabular com: arquivo, período, total de agendas, total de profissionais, data/hora de envio e status
- Abas separadas para Consultas e Cirurgias/Exames
- Status possíveis: `Pendente` · `Confirmado` · `Erro` · `Ignorado`

---

### Módulo 2 — Relatório de Produção (`relatorio_producao.py`)

Geração de planilha XLSX formatada para prestação de contas ao gestor.

- Seleção de prestador e período (mês/ano)
- Período de apuração: **dia 21 do mês selecionado ao dia 20 do mês seguinte**
- Arquivo gerado com `openpyxl` e entregue como download direto (`Content-Disposition: attachment`)
- Nome de arquivo automático: `relatorio_<empresa>_<mes_ini><ano>_<mes_fim><ano>.xlsx`

---

### Módulo 3 — Cadastro de Prestadores

CRUD completo para gestão de empresas prestadoras de serviços médicos.

#### Dados cadastrais
- Razão social, CNPJ (validação de formato), inscrição municipal e estadual
- Endereço completo (logradouro, número, complemento, bairro, cidade, estado, CEP)
- Contato (telefone, e-mail)
- Representante legal (nome, CPF, CRM) e testemunha

#### Especialidades e serviços
- Múltiplas especialidades médicas por prestador (M2M com `Especialidade`)
- Serviços contratados com: tipo (`consulta` / `cirurgia_pequeno` / `cirurgia_medio` / `exame` / `outro`), descrição, unidade de medida, quantidade estimada/mês, valor unitário, prazo de laudo em dias úteis e modalidade remota/presencial
- Cálculo automático de **valor mensal** e **valor global** (baseado na duração da vigência)

#### Vigência contratual
- Datas de início e fim, número do processo

#### Busca e filtros
- Por nome, CNPJ ou representante (busca textual)
- Por especialidade médica
- Por status (ativo/inativo)

---

### Módulo 4 — Importação de Contratos PDF (`extrator.py`)

Extração automática de dados de contratos PDF no padrão SECONCI-SP, usando `pdfplumber` e `PyMuPDF`.

#### Campos extraídos automaticamente

| Campo | Técnica |
|---|---|
| Razão social | Regex sobre texto extraído |
| CNPJ | Regex com validação de formato |
| Inscrição municipal | Regex contextual |
| Endereço completo | Parsing estruturado por proximidade |
| Representante legal (nome, CPF, CRM) | Regex com normalização Title Case |
| Objeto do contrato | Extração de cláusula específica |
| Vigência (início, fim, meses) | Parsing de datas em português |
| Valor mensal e global | Extração de tabela financeira (seção 3.1) |
| Serviços contratados | Dois formatos de tabela (A e B) + Anexo 1 |
| Prazo de entrega de laudo | Parsing numérico da cláusula de prazo |
| Número do processo | Regex sobre cabeçalho |
| Especialidade médica | Inferência a partir do objeto e serviços |

#### Suporte a DocuSign
- Detecta e extrai metadados de campos DocuSign quando o PDF foi assinado digitalmente pela plataforma

#### Fluxo de importação
1. Upload do PDF → gravação em `media/contratos_pdf/`
2. Extração automática → dados exibidos para revisão
3. Revisar e confirmar → cria o `Prestador` com todos os dados pré-preenchidos
4. Opção de marcar como "Ignorado" sem criar prestador

---

## Modelos de Dados

```
Especialidade
  └── nome, ativa

Prestador
  ├── dados da empresa (razão social, CNPJ, endereço, contato)
  ├── representante legal e testemunha
  ├── especialidades (M2M → Especialidade)
  ├── serviços contratados (FK → ServicoContratado)
  └── vigência (data_inicio, data_fim, numero_processo)

ServicoContratado
  ├── prestador (FK)
  ├── especialidade (FK)
  ├── tipo_servico, descrição, unidade_medida
  ├── quantidade_estimada_mes, valor_unitario
  └── prazo_entrega_laudo_dias, remoto

ContratoUpload
  ├── arquivo PDF, nome_arquivo
  ├── dados extraídos (razão social, CNPJ, objeto, serviços, vigência, valores)
  ├── prestador (FK — preenchido após confirmação)
  └── status (pendente / confirmado / erro / ignorado)

UploadProducao
  ├── arquivo XLS/HTML, nome_arquivo
  ├── tipo (consulta / cirurgia_exame)
  ├── data_inicio_periodo, data_fim_periodo
  ├── total_agendas, total_medicos
  └── status, erro_processamento

ProducaoAgenda
  ├── upload (FK → UploadProducao)
  ├── nome_agenda
  └── 28 campos numéricos (vagas, agendamentos por tipo, recepção por desfecho, altas)

ProducaoMedico
  ├── agenda (FK → ProducaoAgenda)
  ├── nome_medico
  └── 28 campos numéricos (mesma estrutura de ProducaoAgenda)
```

---

## Stack Técnica

| Camada | Tecnologia |
|---|---|
| Framework | Django 5.2 |
| Banco de dados | SQLite (padrão) |
| Leitura de HTML/XLS | pandas 3.x + lxml |
| Leitura de XLS binário | xlrd 1.2 |
| Leitura/escrita XLSX | openpyxl 3.x |
| Extração de PDF | pdfplumber + PyMuPDF + pdfminer.six |
| Criptografia | cryptography + cffi |
| Tipografia | Lato (Google Fonts) |
| Frontend | Django Templates + CSS customizado (sem framework JS externo) |

---

## Instalação

```bash
git clone https://github.com/titonel/cadastro.git
cd cadastro
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### `settings.py`

```python
INSTALLED_APPS = [
    # ...
    "cadastro",
]

MEDIA_URL  = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
```

### `urls.py` principal

```python
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("prestadores/", include("cadastro.urls")),
    path("", RedirectView.as_view(url="/prestadores/", permanent=False)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

## Estrutura de Arquivos

```
cadastro/
├── models.py                   # Todos os modelos de dados
├── views.py                    # Views: prestadores e contratos PDF
├── views_home.py               # Views: home, acompanhamento, relatório
├── urls.py                     # Roteamento completo
├── forms.py                    # Formulários Django
├── admin.py                    # Configuração do Django Admin
├── extrator.py                 # Extração de dados de PDFs de contrato
├── producao_siresp.py          # Parser SIRESP — Consultas
├── producao_siresp_exames.py   # Parser SIRESP — Cirurgias/Exames
├── relatorio_producao.py       # Gerador de relatório XLSX
└── templates/cadastro/
    ├── base.html               # Template base (navbar, CSS global, identidade Âmbar)
    ├── home.html               # Landing page com os 4 módulos
    ├── acompanhamento.html     # Upload e histórico de produção
    ├── relatorio.html          # Seleção de prestador/período para XLSX
    ├── prestador_list.html     # Lista com busca e filtros
    ├── prestador_detail.html   # Detalhe do prestador
    ├── prestador_form.html     # Formulário de criação/edição
    ├── prestador_confirm_delete.html
    ├── contrato_upload.html    # Upload de PDF de contrato
    └── contrato_revisao.html   # Revisão dos dados extraídos
```

---

## Agendas Configuradas

### Consultas (59 agendas)

Anestesiologia · Cardiologia · Cirurgia Geral · Cirurgia Pediátrica · Cirurgia Plástica · Cirurgia Vascular · Coloproctologia · Dermatologia · Endocrinologia · Enfermagem (e subagendas: Biópsia de Próstata, Cardiologia, Cistoscopia, Hipertensão, Microcefalia, Multiorientações, Orientação Cirúrgica, Saúde do Homem) · Farmácia · Gastroclínica · Mastologia · Neurologia · Nutrição · Oftalmologia (e subagendas: Avaliação Cirúrgica, Avaliação Pós-cirúrgica, Catarata, Microcefalia, Pterígio, Reflexo Vermelho, Retina, Sífilis Congênita) · Ortopedia · Otorrinolaringologia · Pneumologia · Serviço Social · Urologia (e subagendas: Avaliação Pós-cirúrgica, Saúde do Homem, Vasectomia) — e respectivas modalidades pós-operatórias, pediátricas e de linha de cuidado.

### Cirurgias e Exames (102 agendas)

Colonoscopia · Pequenas Cirurgias · Agulhamento de Lesão Mamária · Angiografia · Angiotomografia · Audiometria · Avaliação Urodinâmica · Biometria · Campimetria · Cirurgias (Geral, Pediátrica, Plástica, Vascular, Coloproctologia, Dermatologia, Oftalmologia em múltiplos tipos, Ortopedia, Urologia e subtipos) · Ecocardiografia · ECG · EEG · Endoscopia · Holter · Laboratório CEAC · Mamografia · MAPA · Nasofibroscopia · Espirometria · Raio-X · Retinografia · Teste Ergométrico · Tomografia · Ultrassonografias (Doppler geral, Doppler vascular, geral, mamas, musculoesquelético, obstétrico, pediátrico, globo ocular) — e variantes INTERNO / EXTERNO / LC.

---

## Notas de Implementação

### Detecção de formato SIRESP

O SIRESP não exporta XLS binário verdadeiro. Os arquivos são páginas HTML completas renomeadas para `.xls`, que o Excel abre por heurística de conteúdo. A detecção por inspeção de bytes garante o roteamento correto independentemente da extensão.

### Formatação numérica brasileira

`pandas.read_html()` é chamado com `thousands='.'` e `decimal=','` para interpretar corretamente valores como `1.234` (mil e duzentos e trinta e quatro) e `95,51` (percentual com vírgula decimal).

### Profissionais em múltiplas agendas

Um mesmo profissional pode atuar em várias agendas no mesmo período. Cada combinação `(profissional, agenda)` gera um registro independente em `ProducaoMedico`, permitindo análise granular por agenda sem perda de informação.

### Refresh após processamento

Após `processar_upload()` gravar os totais e datas no banco, a view executa `upload.refresh_from_db()` antes de montar a mensagem de confirmação — evitando que o objeto em memória (com contagens zeradas) seja exibido ao usuário.

### Campos contratuais padrão AME/SECONCI

Todos os contratos seguem o padrão SECONCI-SP com cláusulas comuns:
- Período de apuração 21–20
- Pagamento no dia 10 do mês subsequente à entrega do relatório + NF
- Obrigações LGPD (cláusula 8)
- Penalidade de 10% por desassistência sem aviso prévio
- Exigência de corpo clínico uniprofissional
