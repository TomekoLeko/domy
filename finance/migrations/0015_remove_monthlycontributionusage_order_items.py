# Generated manually — monthly usage derived from SettlementAllocation

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0014_settlementallocation'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='monthlycontributionusage',
            name='order_items',
        ),
    ]
