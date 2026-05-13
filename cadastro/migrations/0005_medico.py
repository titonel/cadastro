from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cadastro", "0004_producao_siresp"),
    ]

    operations = [
        migrations.CreateModel(
            name="Medico",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome_completo", models.CharField(max_length=300, verbose_name="Nome Completo")),
                ("cpf", models.CharField(
                    blank=True, max_length=14, unique=True, verbose_name="CPF",
                    validators=[django.core.validators.RegexValidator(
                        r"^(\d{3}\.\d{3}\.\d{3}-\d{2})?$", "Formato: 000.000.000-00"
                    )],
                )),
                ("crm", models.CharField(blank=True, max_length=20, verbose_name="CRM")),
                ("rqe", models.CharField(
                    blank=True, help_text="Registro de Qualificação de Especialista (opcional)",
                    max_length=30, verbose_name="RQE",
                )),
                ("foto", models.ImageField(
                    blank=True, null=True,
                    help_text="Foto de perfil do médico (JPG ou PNG)",
                    upload_to="medicos/fotos/%Y/", verbose_name="Foto",
                )),
                ("telefone", models.CharField(blank=True, max_length=20, verbose_name="Telefone / WhatsApp")),
                ("email", models.EmailField(blank=True, verbose_name="E-mail")),
                ("cep", models.CharField(
                    blank=True, max_length=9, verbose_name="CEP",
                    validators=[django.core.validators.RegexValidator(
                        r"^(\d{5}-\d{3})?$", "Formato: 00000-000"
                    )],
                )),
                ("logradouro",  models.CharField(blank=True, max_length=300, verbose_name="Logradouro")),
                ("numero",      models.CharField(blank=True, max_length=20,  verbose_name="Número")),
                ("complemento", models.CharField(blank=True, max_length=100, verbose_name="Complemento")),
                ("bairro",      models.CharField(blank=True, max_length=150, verbose_name="Bairro")),
                ("cidade",      models.CharField(blank=True, max_length=150, verbose_name="Cidade")),
                ("estado",      models.CharField(blank=True, default="SP", max_length=2, verbose_name="Estado (UF)")),
                ("ativo",       models.BooleanField(default=True, verbose_name="Ativo")),
                ("criado_em",   models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("especialidades", models.ManyToManyField(
                    blank=True, related_name="medicos",
                    to="cadastro.especialidade", verbose_name="Especialidades no AME",
                )),
                ("prestador", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="medicos", to="cadastro.prestador",
                    verbose_name="Empresa Prestadora",
                )),
            ],
            options={
                "verbose_name": "Médico",
                "verbose_name_plural": "Médicos",
                "ordering": ["nome_completo"],
            },
        ),
    ]
