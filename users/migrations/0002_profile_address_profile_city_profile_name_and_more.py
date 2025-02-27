from django.db import migrations, models, connection

def add_fields_safely(apps, schema_editor):
    """Check if columns exist before adding them to prevent duplicate column errors."""
    cursor = connection.cursor()

    table_name = 'users_profile'  # Update with your actual table name if needed
    columns_to_add = {
        'address': models.CharField(blank=True, max_length=255),
        'city': models.CharField(blank=True, max_length=100),
        'name': models.CharField(blank=True, max_length=255),
        'phone': models.CharField(blank=True, max_length=15),
        'postal': models.CharField(blank=True, max_length=6),
    }

    for column_name, field in columns_to_add.items():
        cursor.execute(
            f"SELECT column_name FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
            [table_name, column_name]
        )
        if not cursor.fetchone():  # If the column doesn't exist, add it
            schema_editor.add_field(
                apps.get_model('users', 'Profile'),
                field,
            )

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_fields_safely),
    ]
