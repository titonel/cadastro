from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cadastro", "0005_medico"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgendaMapeamento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("nome_agenda", models.CharField(
                    help_text="Nome exato como aparece no relatório do SIRESP (P05 Produção x Profissional)",
                    max_length=200, verbose_name="Nome da Agenda no SIRESP",
                )),
                ("servico", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="mapeamentos",
                    to="cadastro.servicocontratado",
                    verbose_name="Serviço Contratado",
                )),
            ],
            options={
                "verbose_name": "Mapeamento de Agenda",
                "verbose_name_plural": "Mapeamentos de Agenda",
                "ordering": ["servico", "nome_agenda"],
                "unique_together": {("servico", "nome_agenda")},
            },
        ),
    ]
