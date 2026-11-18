"""
Split `Guest.names` into `first_name` / `last_name` and rename `phone`.

Existing rows are preserved: the free-text name is split on the first space
("James and Eleanor Vance" -> "James" + "and Eleanor Vance") before the old
column is dropped. `phone` is renamed in place so stored numbers survive.
"""

from django.db import migrations, models


def split_names(apps, schema_editor):
    Guest = apps.get_model('accreditation', 'Guest')
    for guest in Guest.objects.all().iterator():
        parts = (guest.names or '').strip().split(None, 1)
        first_name = parts[0][:255] if parts else ''
        last_name = parts[1][:255] if len(parts) > 1 else ''
        Guest.objects.filter(pk=guest.pk).update(
            first_name=first_name,
            last_name=last_name,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('accreditation', '0007_event_flyer'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='guest',
            name='accreditati_event_i_a1f9a0_idx',
        ),
        migrations.RenameField(
            model_name='guest',
            old_name='phone',
            new_name='phone_number',
        ),
        migrations.AddField(
            model_name='guest',
            name='first_name',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='guest',
            name='last_name',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.RunPython(split_names, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='guest',
            name='names',
        ),
        migrations.AddIndex(
            model_name='guest',
            index=models.Index(fields=['event', 'first_name', 'last_name'], name='accreditati_event_i_ad9439_idx'),
        ),
    ]
