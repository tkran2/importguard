"""Connect Alembic to the application's models and database."""

from logging.config import fileConfig

from alembic import context

from importguard.database import engine
from importguard.models import Base

if context.config.config_file_name:
    fileConfig(context.config.config_file_name)

if context.is_offline_mode():
    context.configure(
        url=engine.url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
