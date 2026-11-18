"""
Drop the household fields from `Guest` and delete the `Kid` model.

This is intentionally destructive: the four `Guest` columns are removed and the
`accreditation_kid` table is dropped. Apply it only once the dashboard and the
mobile clients no longer read spouse/nanny/allergy/kid data.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accreditation', '0008_guest_first_last_name'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='guest',
            name='allergies',
        ),
        migrations.RemoveField(
            model_name='guest',
            name='nanny_count',
        ),
        migrations.RemoveField(
            model_name='guest',
            name='nanny_name',
        ),
        migrations.RemoveField(
            model_name='guest',
            name='spouse_name',
        ),
        migrations.DeleteModel(
            name='Kid',
        ),
    ]
