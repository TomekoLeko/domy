# Generated by Django 5.1.3 on 2025-03-06 11:05

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('finance', '0006_invoice'),
        ('products', '0007_alter_productimage_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='Supplier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('address', models.CharField(max_length=255)),
                ('postal', models.CharField(max_length=10)),
                ('city', models.CharField(max_length=100)),
                ('mail', models.EmailField(max_length=254)),
                ('phone', models.CharField(max_length=20)),
                ('nip', models.CharField(max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Dostawca',
                'verbose_name_plural': 'Dostawcy',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='StockEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField()),
                ('net_cost', models.DecimalField(decimal_places=2, max_digits=10)),
                ('gross_cost', models.DecimalField(decimal_places=2, max_digits=10)),
                ('stock_type', models.CharField(choices=[('physical', 'Fizyczny'), ('virtual', 'Wirtualny')], max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('remaining_quantity', models.PositiveIntegerField()),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stock_entries', to='products.product')),
            ],
            options={
                'verbose_name': 'Przyjęcie towaru',
                'verbose_name_plural': 'Przyjęcia towaru',
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='StockReduction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stock_reductions', to='products.order')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stock_reductions', to='products.product')),
                ('stock_entry', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reductions', to='stock.stockentry')),
            ],
            options={
                'verbose_name': 'Wydanie towaru',
                'verbose_name_plural': 'Wydania towaru',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SupplyOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('invoice', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='supply_orders', to='finance.invoice')),
                ('supplier', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='supply_orders', to='stock.supplier')),
            ],
            options={
                'verbose_name': 'Zamówienie od dostawcy',
                'verbose_name_plural': 'Zamówienia od dostawców',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='stockentry',
            name='supply_order',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stock_entries', to='stock.supplyorder'),
        ),
    ]
