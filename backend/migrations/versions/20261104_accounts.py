"""Preserve legacy finance data while adopting the current Accounts API."""

from datetime import datetime, timezone
from decimal import Decimal

from alembic import op
import sqlalchemy as sa

revision = "20261104_accounts"
down_revision = None
branch_labels = None
depends_on = None


def columns(connection, name):
    return {
        item["name"]: item
        for item in sa.inspect(connection).get_columns(name)
    }


def reflect(connection, name):
    return sa.Table(
        name,
        sa.MetaData(),
        autoload_with=connection,
    )


def account_fk(connection):
    for key in sa.inspect(connection).get_foreign_keys(
        "transactions"
    ):
        if key["constrained_columns"] == ["account_id"]:
            return key

    return None


def upgrade():
    connection = op.get_bind()
    tables = set(
        sa.inspect(connection).get_table_names()
    )

    required = {
        "users",
        "accounts",
        "financial_accounts",
        "transactions",
        "categories",
    }

    if not required.issubset(tables):
        raise RuntimeError(
            "This repair requires the legacy/current tables "
            "shown in your schema output"
        )

    tx_columns = columns(connection, "transactions")

    required_transaction_columns = {
        "id",
        "user_id",
        "account_id",
        "name",
        "category_id",
        "occurred_on",
        "deleted_at",
    }

    if not required_transaction_columns.issubset(tx_columns):
        raise RuntimeError(
            "Unexpected transactions schema; "
            "repair stopped before changing data"
        )

    original_fk = account_fk(connection)

    if (
        original_fk
        and original_fk["referred_table"]
        not in ["financial_accounts", "accounts"]
    ):
        raise RuntimeError(
            "Unexpected transaction account foreign key"
        )

    if (
        original_fk
        and original_fk["referred_table"] == "accounts"
        and "account_legacy_map" not in tables
    ):
        raise RuntimeError(
            "Transactions already use accounts without a legacy "
            "mapping; do not guess account ownership"
        )

    account_columns = columns(connection, "accounts")

    with op.batch_alter_table("accounts") as batch:
        if "is_archived" not in account_columns:
            batch.add_column(
                sa.Column(
                    "is_archived",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("0"),
                )
            )

        if (
            getattr(
                account_columns["opening_balance"]["type"],
                "precision",
                None,
            )
            != 14
        ):
            batch.alter_column(
                "opening_balance",
                existing_type=account_columns[
                    "opening_balance"
                ]["type"],
                type_=sa.Numeric(14, 2),
                existing_nullable=False,
            )

    if "account_transfer_records" not in tables:
        op.create_table(
            "account_transfer_records",
            sa.Column(
                "id",
                sa.Integer(),
                primary_key=True,
                autoincrement=True,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column(
                "from_account_id",
                sa.Integer(),
                sa.ForeignKey("accounts.id"),
                nullable=False,
            ),
            sa.Column(
                "to_account_id",
                sa.Integer(),
                sa.ForeignKey("accounts.id"),
                nullable=False,
            ),
            sa.Column(
                "amount",
                sa.Numeric(14, 2),
                nullable=False,
            ),
            sa.Column(
                "currency",
                sa.String(3),
                nullable=False,
            ),
            sa.Column(
                "txn_date",
                sa.Date(),
                nullable=False,
            ),
            sa.Column(
                "description",
                sa.String(255),
                nullable=False,
            ),
            sa.Column(
                "client_request_id",
                sa.String(36),
                nullable=True,
            ),
            sa.Column(
                "legacy_transfer_id",
                sa.Integer(),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "user_id",
                "client_request_id",
                name="uq_transfer_user_request",
            ),
            sa.UniqueConstraint(
                "legacy_transfer_id",
                name="uq_transfer_legacy_id",
            ),
        )

        op.create_index(
            "ix_account_transfer_records_user_id",
            "account_transfer_records",
            ["user_id"],
        )

    else:
        header_columns = columns(
            connection,
            "account_transfer_records",
        )

        expected = {
            "id",
            "user_id",
            "from_account_id",
            "to_account_id",
            "amount",
            "currency",
            "txn_date",
            "description",
            "client_request_id",
            "created_at",
        }

        if not expected.issubset(header_columns):
            raise RuntimeError(
                "Existing transfer table differs; "
                "no transfer records were overwritten"
            )

        if "legacy_transfer_id" not in header_columns:
            with op.batch_alter_table(
                "account_transfer_records"
            ) as batch:
                batch.add_column(
                    sa.Column(
                        "legacy_transfer_id",
                        sa.Integer(),
                        nullable=True,
                    )
                )

                batch.create_unique_constraint(
                    "uq_transfer_legacy_id",
                    ["legacy_transfer_id"],
                )

    if "account_legacy_map" not in tables:
        op.create_table(
            "account_legacy_map",
            sa.Column(
                "legacy_account_id",
                sa.Integer(),
                primary_key=True,
            ),
            sa.Column(
                "account_id",
                sa.Integer(),
                sa.ForeignKey("accounts.id"),
                nullable=False,
                unique=True,
            ),
        )

    tx_columns = columns(connection, "transactions")

    unique_sets = [
        set(item["column_names"])
        for item in sa.inspect(
            connection
        ).get_unique_constraints("transactions")
    ]

    unique_sets += [
        set(item["column_names"])
        for item in sa.inspect(
            connection
        ).get_indexes("transactions")
        if item.get("unique")
    ]

    transfer_fk_exists = any(
        key["constrained_columns"] == ["transfer_id"]
        for key in sa.inspect(
            connection
        ).get_foreign_keys("transactions")
    )

    with op.batch_alter_table("transactions") as batch:
        new_columns = [
            ("category", sa.String(100)),
            ("description", sa.String(255)),
            ("transfer_id", sa.Integer()),
            ("legacy_financial_account_id", sa.Integer()),
        ]

        for name, kind in new_columns:
            if name not in tx_columns:
                batch.add_column(
                    sa.Column(
                        name,
                        kind,
                        nullable=True,
                    )
                )

        if (
            getattr(
                tx_columns["amount"]["type"],
                "precision",
                None,
            )
            != 14
        ):
            batch.alter_column(
                "amount",
                existing_type=tx_columns["amount"]["type"],
                type_=sa.Numeric(14, 2),
                existing_nullable=False,
            )

        if (
            getattr(
                tx_columns["kind"]["type"],
                "length",
                0,
            )
            < 20
        ):
            batch.alter_column(
                "kind",
                existing_type=tx_columns["kind"]["type"],
                type_=sa.String(20),
                existing_nullable=False,
            )

        if not transfer_fk_exists:
            batch.create_foreign_key(
                "fk_transaction_transfer",
                "account_transfer_records",
                ["transfer_id"],
                ["id"],
            )

        if {"transfer_id", "kind"} not in unique_sets:
            batch.create_unique_constraint(
                "uq_transaction_transfer_kind",
                ["transfer_id", "kind"],
            )

    transfer_index_exists = any(
        item["column_names"] == ["transfer_id"]
        for item in sa.inspect(
            connection
        ).get_indexes("transactions")
    )

    if not transfer_index_exists:
        op.create_index(
            "ix_transactions_transfer_id",
            "transactions",
            ["transfer_id"],
        )

    accounts = reflect(connection, "accounts")
    old_accounts = reflect(connection, "financial_accounts")
    mapping = reflect(connection, "account_legacy_map")
    users = reflect(connection, "users")

    user_rows = {
        item["id"]: item
        for item in connection.execute(
            sa.select(users)
        ).mappings()
    }

    mapped = {
        item["legacy_account_id"]: item["account_id"]
        for item in connection.execute(
            sa.select(mapping)
        ).mappings()
    }

    legacy_rows = list(
        connection.execute(
            sa.select(old_accounts)
        ).mappings()
    )

    legacy_owners = {
        item["id"]: item["user_id"]
        for item in legacy_rows
    }

    # Old/new IDs can overlap; use a persistent explicit mapping.
    for item in legacy_rows:
        if item["user_id"] not in user_rows:
            raise RuntimeError(
                "Legacy account has no valid owner"
            )

        if item["id"] in mapped:
            target_owner = connection.scalar(
                sa.select(accounts.c.user_id).where(
                    accounts.c.id == mapped[item["id"]]
                )
            )

            if target_owner != item["user_id"]:
                raise RuntimeError(
                    "Existing legacy account mapping "
                    "has an ownership mismatch"
                )

            continue

        currency = (
            user_rows[item["user_id"]].get("currency")
            or "LKR"
        )

        result = connection.execute(
            accounts.insert().values(
                user_id=item["user_id"],
                name=item["name"],
                kind=item["kind"],
                opening_balance=item["opening_balance"],
                currency=currency,
                is_archived=bool(item["archived"]),
            )
        )

        new_id = result.lastrowid

        connection.execute(
            mapping.insert().values(
                legacy_account_id=item["id"],
                account_id=new_id,
            )
        )

        mapped[item["id"]] = new_id

    transactions = reflect(connection, "transactions")
    categories = reflect(connection, "categories")

    names = {
        (item["user_id"], item["id"]): item["name"]
        for item in connection.execute(
            sa.select(categories)
        ).mappings()
    }

    text_rows = list(
        connection.execute(
            sa.select(transactions)
        ).mappings()
    )

    for item in text_rows:
        values = {}

        if not item["category"]:
            values["category"] = (
                names.get(
                    (item["user_id"], item["category_id"])
                )
                or "Other"
            )

        if item["description"] is None:
            values["description"] = item["name"] or ""

        if values:
            connection.execute(
                transactions.update()
                .where(
                    transactions.c.id == item["id"]
                )
                .values(**values)
            )

    foreign_key = account_fk(connection)

    if (
        foreign_key is None
        or foreign_key["referred_table"] == "financial_accounts"
    ):
        if foreign_key:
            with op.batch_alter_table(
                "transactions"
            ) as batch:
                batch.drop_constraint(
                    foreign_key["name"],
                    type_="foreignkey",
                )

        transactions = reflect(
            connection,
            "transactions",
        )

        # Snapshot first so overlapping IDs cannot be remapped twice.
        pending = list(
            connection.execute(
                sa.select(transactions).where(
                    transactions.c.legacy_financial_account_id.is_(
                        None
                    )
                )
            ).mappings()
        )

        for item in pending:
            old_id = item["account_id"]

            if (
                old_id not in mapped
                or legacy_owners.get(old_id) != item["user_id"]
            ):
                raise RuntimeError(
                    "Legacy transaction account/owner mismatch; "
                    "no guessed mapping was applied"
                )

            connection.execute(
                transactions.update()
                .where(
                    transactions.c.id == item["id"]
                )
                .values(
                    account_id=mapped[old_id],
                    legacy_financial_account_id=old_id,
                )
            )

        with op.batch_alter_table(
            "transactions"
        ) as batch:
            batch.create_foreign_key(
                "fk_transactions_account",
                "accounts",
                ["account_id"],
                ["id"],
            )

    transactions = reflect(connection, "transactions")

    bad_owner = connection.execute(
        sa.select(transactions.c.id)
        .select_from(
            transactions.outerjoin(
                accounts,
                accounts.c.id == transactions.c.account_id,
            )
        )
        .where(
            sa.or_(
                accounts.c.id.is_(None),
                accounts.c.user_id != transactions.c.user_id,
            )
        )
        .limit(1)
    ).first()

    if bad_owner:
        raise RuntimeError(
            "A transaction points to a missing account "
            "or a different user"
        )

    tx_columns = columns(connection, "transactions")

    with op.batch_alter_table(
        "transactions"
    ) as batch:
        for name, kind, default in [
            ("category", sa.String(100), "Other"),
            ("description", sa.String(255), ""),
        ]:
            if tx_columns[name]["nullable"]:
                batch.alter_column(
                    name,
                    existing_type=kind,
                    nullable=False,
                    server_default=default,
                )

    if "account_transfers" in tables:
        old_transfers = reflect(
            connection,
            "account_transfers",
        )
        headers = reflect(
            connection,
            "account_transfer_records",
        )
        transactions = reflect(
            connection,
            "transactions",
        )

        active = list(
            connection.execute(
                sa.select(old_transfers).where(
                    old_transfers.c.reversed_at.is_(None)
                )
            ).mappings()
        )

        for item in active:
            existing_id = connection.scalar(
                sa.select(headers.c.id).where(
                    headers.c.legacy_transfer_id == item["id"]
                )
            )

            if existing_id is not None:
                count = connection.scalar(
                    sa.select(sa.func.count())
                    .select_from(transactions)
                    .where(
                        transactions.c.transfer_id == existing_id
                    )
                )

                if count != 2:
                    raise RuntimeError(
                        "An imported legacy transfer is incomplete; "
                        "inspect before retrying"
                    )

                continue

            if (
                legacy_owners.get(item["from_id"])
                != item["user_id"]
                or legacy_owners.get(item["to_id"])
                != item["user_id"]
                or Decimal(item["amount"]) <= 0
            ):
                raise RuntimeError(
                    "Legacy transfer has invalid ownership or amount"
                )

            created = datetime.now(
                timezone.utc
            ).replace(tzinfo=None)

            currency = (
                user_rows[item["user_id"]].get("currency")
                or "LKR"
            )

            transfer_id = connection.execute(
                headers.insert().values(
                    user_id=item["user_id"],
                    from_account_id=mapped[item["from_id"]],
                    to_account_id=mapped[item["to_id"]],
                    amount=item["amount"],
                    currency=currency,
                    txn_date=item["occurred_on"],
                    description="Imported legacy transfer",
                    client_request_id=None,
                    legacy_transfer_id=item["id"],
                    created_at=created,
                )
            ).lastrowid

            for kind, old_id in [
                ("transfer_out", item["from_id"]),
                ("transfer_in", item["to_id"]),
            ]:
                connection.execute(
                    transactions.insert().values(
                        user_id=item["user_id"],
                        account_id=mapped[old_id],
                        category_id=None,
                        name="Imported legacy transfer",
                        kind=kind,
                        amount=item["amount"],
                        occurred_on=item["occurred_on"],
                        deleted_at=None,
                        created_at=created,
                        category="Transfer",
                        description="Imported legacy transfer",
                        transfer_id=transfer_id,
                        legacy_financial_account_id=old_id,
                    )
                )

    print(
        "Accounts repair complete: existing accounts kept; "
        "legacy accounts/transactions/transfers mapped safely."
    )


def downgrade():
    raise RuntimeError(
        "Automatic downgrade is disabled for this data-mapping "
        "repair; use a verified database backup to restore "
        "the old layout"
    )