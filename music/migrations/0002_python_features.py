from django.db import migrations, models
import uuid

GENRES = [
    "Поп", "Рок", "Хип-хоп", "Электронная", "Инди", "Джаз", "Классика", "R&B", "Метал", "Панк",
    "Фолк", "Кантри", "Латина", "K-pop", "Саундтреки", "Регги", "Блюз", "Другое",
]


def seed_genres(apps, schema_editor):
    Genre = apps.get_model("music", "Genre")
    for name in GENRES:
        Genre.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [("music", "0001_initial")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    ALTER TABLE messages ADD COLUMN IF NOT EXISTS submission_id uuid;
                    CREATE UNIQUE INDEX IF NOT EXISTS messages_submission_id_key ON messages (submission_id);
                    CREATE TABLE IF NOT EXISTS music_rate_buckets (
                      key varchar(64) PRIMARY KEY,
                      hits integer NOT NULL DEFAULT 0 CHECK (hits >= 0),
                      expires_at timestamptz NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS music_rate_buckets_expires_at_idx ON music_rate_buckets (expires_at);
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunPython(seed_genres, reverse_code=migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="message",
                    name="submission_id",
                    field=models.UUIDField(blank=True, null=True, unique=True),
                ),
                migrations.CreateModel(
                    name="RateBucket",
                    fields=[
                        ("key", models.CharField(max_length=64, primary_key=True, serialize=False)),
                        ("hits", models.PositiveIntegerField(default=0)),
                        ("expires_at", models.DateTimeField(db_index=True)),
                    ],
                    options={"db_table": "music_rate_buckets"},
                ),
            ],
        )
    ]
