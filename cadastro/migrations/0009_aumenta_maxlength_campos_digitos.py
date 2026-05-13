from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("cadastro", "0008_limpar_formatacao_campos"),
    ]

    operations = [
        migrations.AlterField(
            model_name="prestador", name="cnpj",
            field=models.CharField(
                max_length=20, unique=True, verbose_name="CNPJ",
                validators=[django.core.validators.RegexValidator(
                    r"^\d{14}$", "Informe os 14 dígitos do CNPJ"
                )],
            ),
        ),
        migrations.AlterField(
            model_name="prestador", name="cep",
            field=models.CharField(blank=True, max_length=20, verbose_name="CEP"),
        ),
        migrations.AlterField(
            model_name="prestador", name="cpf_representante",
            field=models.CharField(blank=True, max_length=20, verbose_name="CPF do Representante"),
        ),
        migrations.AlterField(
            model_name="prestador", name="telefone",
            field=models.CharField(blank=True, max_length=20, verbose_name="Telefone"),
        ),
        migrations.AlterField(
            model_name="prestador", name="telefone_testemunha",
            field=models.CharField(blank=True, max_length=20, verbose_name="Telefone da Testemunha"),
        ),
        migrations.AlterField(
            model_name="medico", name="cpf",
            field=models.CharField(
                blank=True, max_length=20, unique=True, verbose_name="CPF",
            ),
        ),
        migrations.AlterField(
            model_name="medico", name="cep",
            field=models.CharField(blank=True, max_length=20, verbose_name="CEP"),
        ),
        migrations.AlterField(
            model_name="medico", name="telefone",
            field=models.CharField(blank=True, max_length=20, verbose_name="Telefone / WhatsApp"),
        ),
    ]
