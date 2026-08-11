from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0006_add_operational_cost_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='Vacation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField(verbose_name='Data od')),
                ('end_date', models.DateField(verbose_name='Data do')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Urlop',
                'verbose_name_plural': 'Urlopy',
                'ordering': ['start_date'],
            },
        ),
    ]
