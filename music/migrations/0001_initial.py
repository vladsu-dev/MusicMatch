from django.db import migrations, models, connection
import django.db.models.deletion
import django.utils.timezone
import uuid

GENRES = [
    "Поп", "Рок", "Хип-хоп", "Электронная", "Инди", "Джаз", "Классика", "R&B", "Метал", "Панк",
    "Фолк", "Кантри", "Латина", "K-pop", "Саундтреки", "Регги", "Блюз", "Другое",
]

SCHEMA_SQL = """
CREATE TABLE users (
  id uuid PRIMARY KEY,
  email varchar(254) NOT NULL UNIQUE,
  password_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT users_email_lower_check CHECK (email = lower(email))
);

CREATE TABLE genres (
  name varchar(40) PRIMARY KEY
);

INSERT INTO genres (name) VALUES
  ('Поп'), ('Рок'), ('Хип-хоп'), ('Электронная'), ('Инди'), ('Джаз'), ('Классика'), ('R&B'), ('Метал'), ('Панк'),
  ('Фолк'), ('Кантри'), ('Латина'), ('K-pop'), ('Саундтреки'), ('Регги'), ('Блюз'), ('Другое')
ON CONFLICT (name) DO NOTHING;

CREATE TABLE profiles (
  user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  name varchar(40) NOT NULL,
  genre varchar(40) NOT NULL REFERENCES genres(name),
  photo text NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT profiles_name_length_check CHECK (char_length(name) BETWEEN 2 AND 40),
  CONSTRAINT profiles_photo_size_check CHECK (octet_length(photo) <= 1400000)
);
CREATE INDEX profiles_genre_idx ON profiles (genre);

CREATE TABLE sessions (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  refresh_hash char(64) NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX sessions_user_idx ON sessions (user_id);
CREATE INDEX sessions_expiry_idx ON sessions (expires_at);

CREATE TABLE decisions (
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  target_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  action varchar(4) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, target_id),
  CONSTRAINT decisions_action_check CHECK (action IN ('like', 'skip')),
  CONSTRAINT decisions_not_self_check CHECK (user_id <> target_id)
);

CREATE TABLE matches (
  id uuid PRIMARY KEY,
  user_low uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  user_high uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT matches_order_check CHECK (user_low < user_high),
  CONSTRAINT matches_pair_unique UNIQUE (user_low, user_high)
);
CREATE INDEX matches_high_idx ON matches (user_high);

CREATE TABLE messages (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  match_id uuid NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
  sender_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  text varchar(2000) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT messages_text_length_check CHECK (char_length(trim(text)) BETWEEN 1 AND 2000)
);
CREATE INDEX messages_match_id_idx ON messages (match_id, id DESC);
"""

MUSIC_TABLES = {"users", "genres", "profiles", "sessions", "decisions", "matches", "messages"}
EXPECTED_COLUMNS = {
    "users": {"id": "uuid", "email": "varchar", "password_hash": "text", "created_at": "timestamptz"},
    "genres": {"name": "varchar"},
    "profiles": {"user_id": "uuid", "name": "varchar", "genre": "varchar", "photo": "text", "updated_at": "timestamptz"},
    "sessions": {"id": "uuid", "user_id": "uuid", "refresh_hash": "bpchar", "expires_at": "timestamptz", "created_at": "timestamptz"},
    "decisions": {"user_id": "uuid", "target_id": "uuid", "action": "varchar", "created_at": "timestamptz"},
    "matches": {"id": "uuid", "user_low": "uuid", "user_high": "uuid", "created_at": "timestamptz"},
    "messages": {"id": "int8", "match_id": "uuid", "sender_id": "uuid", "text": "varchar", "created_at": "timestamptz"},
}


def create_or_adopt_schema(apps, schema_editor):
    if connection.vendor != "postgresql":
        raise RuntimeError("MusicMatch uses PostgreSQL. Set DATABASE_URL to a PostgreSQL database.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(730214)")
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name = ANY(%s)
            """,
            [list(MUSIC_TABLES)],
        )
        existing = {row[0] for row in cursor.fetchall()}
        if not existing:
            cursor.execute(SCHEMA_SQL)
            return
        if existing != MUSIC_TABLES:
            missing = ", ".join(sorted(MUSIC_TABLES - existing))
            present = ", ".join(sorted(existing))
            raise RuntimeError(f"Database has only part of MusicMatch schema. Present: {present}. Missing: {missing}.")

        cursor.execute(
            """
            SELECT table_name, column_name, udt_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = ANY(%s)
            """,
            [list(MUSIC_TABLES)],
        )
        actual = {}
        for table, column, udt in cursor.fetchall():
            actual.setdefault(table, {})[column] = udt
        errors = []
        for table, columns in EXPECTED_COLUMNS.items():
            for column, expected_type in columns.items():
                found = actual.get(table, {}).get(column)
                if found != expected_type:
                    errors.append(f"{table}.{column}: expected {expected_type}, found {found or 'missing'}")
        if errors:
            raise RuntimeError("Existing database does not match MusicMatch schema: " + "; ".join(errors))


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(create_or_adopt_schema, reverse_code=migrations.RunPython.noop)],
            state_operations=[
                migrations.CreateModel(
                    name="Account",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("email", models.EmailField(max_length=254, unique=True)),
                        ("password_hash", models.TextField()),
                        ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                    ],
                    options={"db_table": "users", "ordering": ["-created_at"]},
                ),
                migrations.CreateModel(
                    name="Genre",
                    fields=[("name", models.CharField(max_length=40, primary_key=True, serialize=False))],
                    options={"db_table": "genres", "ordering": ["name"]},
                ),
                migrations.CreateModel(
                    name="Profile",
                    fields=[
                        ("user", models.OneToOneField(db_column="user_id", on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name="profile", serialize=False, to="music.account")),
                        ("name", models.CharField(max_length=40)),
                        ("photo", models.TextField()),
                        ("updated_at", models.DateTimeField(default=django.utils.timezone.now)),
                        ("genre", models.ForeignKey(db_column="genre", on_delete=django.db.models.deletion.PROTECT, to="music.genre")),
                    ],
                    options={"db_table": "profiles", "ordering": ["name"]},
                ),
                migrations.CreateModel(
                    name="LoginSession",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("refresh_hash", models.CharField(max_length=64, unique=True)),
                        ("expires_at", models.DateTimeField()),
                        ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                        ("user", models.ForeignKey(db_column="user_id", on_delete=django.db.models.deletion.CASCADE, related_name="login_sessions", to="music.account")),
                    ],
                    options={"db_table": "sessions"},
                ),
                migrations.CreateModel(
                    name="Decision",
                    fields=[
                        ("pk", models.CompositePrimaryKey("user", "target", blank=True, editable=False, primary_key=True, serialize=False)),
                        ("action", models.CharField(choices=[("like", "Нравится"), ("skip", "Пропустить")], max_length=4)),
                        ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                        ("target", models.ForeignKey(db_column="target_id", on_delete=django.db.models.deletion.CASCADE, related_name="decisions_received", to="music.account")),
                        ("user", models.ForeignKey(db_column="user_id", on_delete=django.db.models.deletion.CASCADE, related_name="decisions_made", to="music.account")),
                    ],
                    options={"db_table": "decisions"},
                ),
                migrations.CreateModel(
                    name="Match",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                        ("user_high", models.ForeignKey(db_column="user_high", on_delete=django.db.models.deletion.CASCADE, related_name="matches_as_high", to="music.account")),
                        ("user_low", models.ForeignKey(db_column="user_low", on_delete=django.db.models.deletion.CASCADE, related_name="matches_as_low", to="music.account")),
                    ],
                    options={"db_table": "matches", "ordering": ["-created_at"], "unique_together": {("user_low", "user_high")}},
                ),
                migrations.CreateModel(
                    name="Message",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        ("text", models.CharField(max_length=2000)),
                        ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                        ("match", models.ForeignKey(db_column="match_id", on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="music.match")),
                        ("sender", models.ForeignKey(db_column="sender_id", on_delete=django.db.models.deletion.CASCADE, related_name="sent_messages", to="music.account")),
                    ],
                    options={"db_table": "messages", "ordering": ["id"]},
                ),
                migrations.AddIndex(model_name="profile", index=models.Index(fields=["genre"], name="profiles_genre_idx")),
                migrations.AddIndex(model_name="loginsession", index=models.Index(fields=["user"], name="sessions_user_idx")),
                migrations.AddIndex(model_name="loginsession", index=models.Index(fields=["expires_at"], name="sessions_expiry_idx")),
                migrations.AddIndex(model_name="match", index=models.Index(fields=["user_high"], name="matches_high_idx")),
                migrations.AddIndex(model_name="message", index=models.Index(fields=["match", "-id"], name="messages_match_id_idx")),
            ],
        )
    ]
