from collections import defaultdict

from django.db import migrations, models
from django.db.models import Q


def backfill_order_numbers(apps, schema_editor):
    Order = apps.get_model('products', 'Order')
    orders = list(
        Order.objects.filter(Q(order_number__isnull=True) | Q(order_number=''))
    )
    orders.sort(key=lambda order: (order.created_at, order.id))

    counters = defaultdict(int)
    for order in orders:
        created_at = order.created_at
        key = (created_at.year, created_at.month)
        counters[key] += 1
        sequence = str(counters[key]).zfill(2)
        order.order_number = f"{sequence}/{str(created_at.month).zfill(2)}/{created_at.year}"
        order.save(update_fields=['order_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0017_product_type_remove_is_service'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='order_number',
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
        migrations.RunPython(backfill_order_numbers, migrations.RunPython.noop),
    ]
