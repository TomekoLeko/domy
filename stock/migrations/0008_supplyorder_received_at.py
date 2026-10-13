from django.db import migrations, models
import django.utils.timezone


def backfill_received_at_from_created_at(apps, schema_editor):
    SupplyOrder = apps.get_model('stock', 'SupplyOrder')
    from django.utils import timezone as dj_tz

    for supply_order in SupplyOrder.objects.all().iterator():
        created = supply_order.created_at
        if created is None:
            continue
        if dj_tz.is_aware(created):
            supply_order.received_at = dj_tz.localtime(created).date()
        else:
            supply_order.received_at = created.date()
        supply_order.save(update_fields=['received_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0007_vacation'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplyorder',
            name='received_at',
            field=models.DateField(
                default=django.utils.timezone.localdate,
                verbose_name='Data przyjęcia',
            ),
        ),
        migrations.RunPython(backfill_received_at_from_created_at, migrations.RunPython.noop),
    ]
