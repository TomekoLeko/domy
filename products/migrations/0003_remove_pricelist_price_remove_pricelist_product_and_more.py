# Generated by Django 5.1.3 on 2024-12-18 15:06

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_productimage_image'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='pricelist',
            name='price',
        ),
        migrations.RemoveField(
            model_name='pricelist',
            name='product',
        ),
        migrations.AlterField(
            model_name='pricelist',
            name='name',
            field=models.CharField(max_length=50, unique=True),
        ),
        migrations.CreateModel(
            name='Price',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('net_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('gross_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('price_list', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prices', to='products.pricelist')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prices', to='products.product')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('price_list', 'product'), name='unique_price_per_product_per_list')],
            },
        ),
    ]