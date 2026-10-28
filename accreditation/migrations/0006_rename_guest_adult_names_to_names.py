"""
Rename `Guest.adult_names` to `Guest.names`.

`RenameField` emits `ALTER TABLE ... RENAME COLUMN` (Postgres) /
`ALTER TABLE ... RENAME COLUMN` (SQLite 3.25+), so every existing guest keeps
its names. It must never be replaced with RemoveField + AddField, which would
drop the column and with it every stored guest name.

The dependent index is dropped and recreated only because Django derives index
names from the column list; no guest rows are touched by that.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accreditation', '0005_alter_organizerapikey_options'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='guest',
            name='accreditati_event_i_30231e_idx',
        ),
        migrations.RenameField(
            model_name='guest',
            old_name='adult_names',
            new_name='names',
        ),
        migrations.AddIndex(
            model_name='guest',
            index=models.Index(
                fields=['event', 'names'],
                name='accreditati_event_i_a1f9a0_idx',
            ),
        ),
    ]
