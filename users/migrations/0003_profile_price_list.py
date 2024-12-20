# Generated by Django 5.1.3 on 2024-12-20 10:49

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_remove_pricelist_price_remove_pricelist_product_and_more'),
        ('users', '0002_profile_address_profile_city_profile_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='price_list',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='products.pricelist'),
        ),
    ]
