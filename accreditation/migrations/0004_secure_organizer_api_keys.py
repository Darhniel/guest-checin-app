from django.db import migrations, models
import django.conf
import django.db.models.deletion
import secrets

from accreditation.models import hash_api_key


def convert_plaintext_keys(apps, schema_editor):
    """Hash the stored plaintext keys, keep an identification prefix row."""
    OrganizerAPIKey = apps.get_model('accreditation', 'OrganizerAPIKey')
    for row in OrganizerAPIKey.objects.all():
        # Historical rows may hold an empty key (never issued); give them an
        # unusable random digest so they can never authenticate.
        raw = row.key or secrets.token_hex(32)
        row.key_hash = hash_api_key(raw)
        row.key_prefix = raw[:8]
        row.save(update_fields=['key_hash', 'key_prefix'])


class Migration(migrations.Migration):

    dependencies = [
        ('accreditation', '0003_guestcategory_is_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizerapikey',
            name='key_hash',
            field=models.CharField(default='pending-migration', max_length=64, unique=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='organizerapikey',
            name='key_prefix',
            field=models.CharField(default='', max_length=12),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='organizerapikey',
            name='created_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='organizer_api_keys',
                to=django.conf.settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(convert_plaintext_keys, migrations.RunPython.noop),
        # The plaintext key column is retired: only hashes live at rest now.
        migrations.RemoveField(model_name='organizerapikey', name='key'),
    ]
