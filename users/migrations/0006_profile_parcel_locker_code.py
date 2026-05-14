from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_profile_discount_rate_percent"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="parcel_locker_code",
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
