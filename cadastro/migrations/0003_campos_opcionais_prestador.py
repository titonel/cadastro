from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("cadastro", "0002_contratoupload"),
    ]

    operations = [
        # Endereço
        migrations.AlterField(
            model_name="prestador",
            name="logradouro",
            field=models.CharField(blank=True, max_length=300, verbose_name="Logradouro"),
        ),
        migrations.AlterField(
            model_name="prestador",
            name="numero",
            field=models.CharField(blank=True, max_length=20, verbose_name="Número"),
        ),
        migrations.AlterField(
            model_name="prestador",
            name="bairro",
            field=models.CharField(blank=True, max_length=150, verbose_name="Bairro"),
        ),
        migrations.AlterField(
            model_name="prestador",
            name="cidade",
            field=models.CharField(blank=True, max_length=150, verbose_name="Cidade"),
        ),
        migrations.AlterField(
            model_name="prestador",
            name="estado",
            field=models.CharField(blank=True, default="SP", max_length=2, verbose_name="Estado (UF)"),
        ),
        migrations.AlterField(
            model_name="prestador",
            name="cep",
            field=models.CharField(
                blank=True,
                max_length=9,
                validators=[django.core.validators.RegexValidator(r"^(\d{5}-\d{3})?$", "Formato: 00000-000")],
                verbose_name="CEP",
            ),
        ),
        # Contato
        migrations.AlterField(
            model_name="prestador",
            name="telefone",
            field=models.CharField(blank=True, max_length=20, verbose_name="Telefone"),
        ),
        migrations.AlterField(
            model_name="prestador",
            name="email",
            field=models.EmailField(blank=True, max_length=254, verbose_name="E-mail"),
        ),
        # Representante Legal
        migrations.AlterField(
            model_name="prestador",
            name="nome_representante",
            field=models.CharField(blank=True, max_length=200, verbose_name="Nome do Representante Legal"),
        ),
        migrations.AlterField(
            model_name="prestador",
            name="cpf_representante",
            field=models.CharField(
                blank=True,
                max_length=14,
                validators=[django.core.validators.RegexValidator(r"^(\d{3}\.\d{3}\.\d{3}-\d{2})?$", "Formato: 000.000.000-00")],
                verbose_name="CPF do Representante",
            ),
        ),
        migrations.AlterField(
            model_name="prestador",
            name="crm_representante",
            field=models.CharField(blank=True, max_length=30, verbose_name="CRM do Representante"),
        ),
        # Testemunha
        migrations.AlterField(
            model_name="prestador",
            name="nome_testemunha",
            field=models.CharField(blank=True, max_length=200, verbose_name="Nome da Testemunha"),
        ),
        migrations.AlterField(
            model_name="prestador",
            name="telefone_testemunha",
            field=models.CharField(blank=True, max_length=20, verbose_name="Telefone da Testemunha"),
        ),
        migrations.AlterField(
            model_name="prestador",
            name="email_testemunha",
            field=models.EmailField(blank=True, max_length=254, verbose_name="E-mail da Testemunha"),
        ),
        # Vigência – permite datas nulas
        migrations.AlterField(
            model_name="prestador",
            name="data_inicio_contrato",
            field=models.DateField(blank=True, null=True, verbose_name="Início da Vigência"),
        ),
        migrations.AlterField(
            model_name="prestador",
            name="data_fim_contrato",
            field=models.DateField(blank=True, null=True, verbose_name="Fim da Vigência"),
        ),
        # ServicoContratado – tipo e descrição opcionais
        migrations.AlterField(
            model_name="servicocontratado",
            name="tipo_servico",
            field=models.CharField(
                blank=True,
                choices=[
                    ("consulta", "Consulta Ambulatorial"),
                    ("cirurgia_pequeno", "Cirurgia de Pequeno Porte"),
                    ("cirurgia_medio", "Cirurgia de Médio Porte"),
                    ("exame", "Exame / Laudo"),
                    ("outro", "Outro"),
                ],
                max_length=30,
                verbose_name="Tipo de Serviço",
            ),
        ),
        migrations.AlterField(
            model_name="servicocontratado",
            name="descricao",
            field=models.CharField(blank=True, max_length=300, verbose_name="Descrição do Serviço"),
        ),
        migrations.AlterField(
            model_name="servicocontratado",
            name="quantidade_estimada_mes",
            field=models.PositiveIntegerField(default=0, verbose_name="Qtde. Estimada/Mês"),
        ),
        migrations.AlterField(
            model_name="servicocontratado",
            name="valor_unitario",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="Valor Unitário (R$)"),
        ),
    ]
