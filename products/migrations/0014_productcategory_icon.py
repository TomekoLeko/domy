from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0013_order_payment_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="productcategory",
            name="icon",
            field=models.CharField(default="tag", max_length=50),
        ),
    ]
