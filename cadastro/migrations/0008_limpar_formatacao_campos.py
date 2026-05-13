"""
Migration 0008 — duas operações:
1. Limpeza de dados: remove pontuação de CPF, CNPJ, CEP e telefone
   nos registros existentes (Prestador e Medico).
2. Redução de max_length dos campos afetados.
"""
import re
from django.db import migrations, models
import django.core.validators


def limpar_dados(apps, schema_editor):
    Prestador = apps.get_model("cadastro", "Prestador")
    Medico    = apps.get_model("cadastro", "Medico")

    def so_digitos(v):
        return re.sub(r"\D", "", v or "")

    for p in Prestador.objects.all():
        alterado = False
        for campo in ("cnpj", "cep", "cpf_representante", "telefone", "telefone_testemunha"):
            orig = getattr(p, campo, "") or ""
            novo = so_digitos(orig)
            if novo != orig:
                setattr(p, campo, novo)
                alterado = True
        if alterado:
            p.save()

    for m in Medico.objects.all():
        alterado = False
        for campo in ("cpf", "cep", "telefone"):
            orig = getattr(m, campo, "") or ""
            novo = so_digitos(orig)
            if novo != orig:
                setattr(m, campo, novo)
                alterado = True
        if alterado:
            m.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("cadastro", "0007_seed_especialidades"),
    ]

    operations = [
        # 1. Limpeza de dados primeiro
        migrations.RunPython(limpar_dados, noop),

        # 2. Redução de max_length — Prestador
        migrations.AlterField(
            model_name="prestador",
            name="cnpj",
            field=models.CharField(
                max_length=14, unique=True, verbose_name="CNPJ",
                validators=[django.core.validators.RegexValidator(
                    r"^\d{14}$", "Informe os 14 dígitos do CNPJ sem pontuação"
                )],
            ),
        ),
        migrations.AlterField(
            model_name="prestador",
            name="cep",
            field=models.CharField(
                blank=True, max_length=8, verbose_name="CEP",
                validators=[django.core.validators.RegexValidator(
                    r"^(\d{8})?$", "Informe os 8 dígitos do CEP"
                )],
            ),
        ),
        migrations.AlterField(
            model_name="prestador",
            name="cpf_representante",
            field=models.CharField(
                blank=True, max_length=11, verbose_name="CPF do Representante",
                validators=[django.core.validators.RegexValidator(
                    r"^(\d{11})?$", "Informe os 11 dígitos do CPF"
                )],
            ),
        ),
        migrations.AlterField(
            model_name="prestador",
            name="telefone",
            field=models.CharField(blank=True, max_length=11, verbose_name="Telefone"),
        ),
        migrations.AlterField(
            model_name="prestador",
            name="telefone_testemunha",
            field=models.CharField(blank=True, max_length=11, verbose_name="Telefone da Testemunha"),
        ),

        # 2. Redução de max_length — Medico
        migrations.AlterField(
            model_name="medico",
            name="cpf",
            field=models.CharField(
                blank=True, max_length=11, unique=True, verbose_name="CPF",
                validators=[django.core.validators.RegexValidator(
                    r"^(\d{11})?$", "Informe os 11 dígitos do CPF"
                )],
            ),
        ),
        migrations.AlterField(
            model_name="medico",
            name="cep",
            field=models.CharField(
                blank=True, max_length=8, verbose_name="CEP",
                validators=[django.core.validators.RegexValidator(
                    r"^(\d{8})?$", "Informe os 8 dígitos do CEP"
                )],
            ),
        ),
        migrations.AlterField(
            model_name="medico",
            name="telefone",
            field=models.CharField(blank=True, max_length=11, verbose_name="Telefone / WhatsApp"),
        ),
    ]
