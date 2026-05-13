"""
Migration de dados: garante que todas as especialidades conhecidas do SIRESP
existam na tabela Especialidade com ativa=True.
Usa get_or_create para não duplicar registros existentes.
"""
from django.db import migrations

ESPECIALIDADES = [
    "Anestesiologia",
    "Cardiologia",
    "Cirurgia Geral",
    "Cirurgia Pediátrica",
    "Cirurgia Plástica",
    "Cirurgia Vascular",
    "Coloproctologia",
    "Dermatologia",
    "Endocrinologia",
    "Enfermagem",
    "Farmácia",
    "Gastroclínica",
    "Mastologia",
    "Neurologia",
    "Neurologia Pediátrica",
    "Nutrição",
    "Oftalmologia",
    "Ortopedia",
    "Otorrinolaringologia",
    "Pneumologia",
    "Pneumologia Pediátrica",
    "Serviço Social",
    "Urologia",
]


def seed_especialidades(apps, schema_editor):
    Especialidade = apps.get_model("cadastro", "Especialidade")
    for nome in ESPECIALIDADES:
        Especialidade.objects.get_or_create(nome=nome, defaults={"ativa": True})


def noop(apps, schema_editor):
    pass  # reversão intencional: não remove registros


class Migration(migrations.Migration):

    dependencies = [
        ("cadastro", "0006_agendamapeamento"),
    ]

    operations = [
        migrations.RunPython(seed_especialidades, noop),
    ]
