from alembic import context

from app.database import Base, engine

import app.models.user
import app.models.finance


target_metadata = Base.metadata


def run_migrations_offline():
    raise RuntimeError(
        "This existing-schema migration requires "
        "an online database connection"
    )


def run_migrations_online():
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()