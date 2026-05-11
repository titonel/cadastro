# Cadastro de Prestadores – AME Caraguatatuba

Sistema Django para gestão de fornecedores/prestadores médicos do AME Caraguatatuba (SECONCI-SP).

## Funcionalidades

- **Cadastro completo** de prestadores com dados da empresa, endereço, representante legal, testemunha
- **Especialidades médicas** múltiplas por prestador
- **Serviços contratados** com tipo, quantidade estimada, valor unitário e prazo de laudo
- **Cálculo automático** de valor mensal e valor global do contrato (baseado na vigência)
- **Busca e filtros** por nome/CNPJ/representante, especialidade e status
- **Admin Django** completo com todos os modelos

## Modelos

| Modelo | Descrição |
|---|---|
| `Especialidade` | Lista de especialidades médicas (ex: Pneumologia Pediátrica, Cardiologia) |
| `Prestador` | Empresa contratada — dados gerais, endereço, representante, testemunha, vigência |
| `ServicoContratado` | Serviços vinculados ao prestador: consultas, exames, cirurgias, laudos |

## Setup

```bash
pip install django
python manage.py makemigrations cadastro
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Adicionar ao `INSTALLED_APPS` do projeto:
```python
INSTALLED_APPS = [
    ...
    "cadastro",
]
```

Adicionar ao `urls.py` principal:
```python
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("prestadores/", include("cadastro.urls")),
]
```

## Campos mapeados dos contratos

Campos **comuns** a todos os contratos AME (padrão SECONCI):
- Dados da empresa (CNPJ, inscrição municipal/estadual, endereço)
- Representante legal (nome, CPF, CRM)
- Período 21–20 para apuração de produção
- Relatório de produção + Nota Fiscal como requisito de pagamento
- Pagamento no dia 10 do mês subsequente
- Obrigações LGPD (cláusula 8)
- Penalidade de 10% por desassistência sem aviso
- Exigência de equipe uniprofissional (médicos como sócios)

Campos **variáveis** por contrato:
- Especialidade médica e tipo de serviço (consulta, laudo, cirurgia)
- Quantidade estimada de procedimentos/mês
- Valor unitário por procedimento
- Prazo de entrega do laudo (5 ou 7 dias úteis)
- Responsabilidade pelos equipamentos (CONTRATANTE vs CONTRATADA)
- Modalidade presencial ou remota do serviço
