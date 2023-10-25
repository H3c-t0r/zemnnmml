"""Remove shared columns [7500f434b71c].

Revision ID: 7500f434b71c
Revises: 0.45.4
Create Date: 2023-10-16 15:15:34.865337

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7500f434b71c"
down_revision = "0.45.5"
branch_labels = None
depends_on = None


def _rename_default_entities(table: sa.Table) -> None:
    """Include owner id in the name of default entities.

    Args:
        table: The table in which to rename the default entities.
    """
    connection = op.get_bind()

    query = sa.select(
        table.c.id,
        table.c.user_id,
    ).where(table.c.name == "default")

    res = connection.execute(query).fetchall()
    for id, owner_id in res:
        name = f"default-{owner_id}"

        connection.execute(
            sa.update(table).where(table.c.id == id).values(name=name)
        )


def resolve_duplicate_names() -> None:
    """Resolve duplicate names for shareable entities."""
    meta = sa.MetaData(bind=op.get_bind())
    meta.reflect(only=("stack", "stack_component", "service_connector"))

    stack_table = sa.Table("stack", meta)
    stack_component_table = sa.Table("stack_component", meta)

    _rename_default_entities(stack_table)
    _rename_default_entities(stack_component_table)

    service_connector_table = sa.Table("service_connector", meta)
    query = sa.select(
        service_connector_table.c.id,
        service_connector_table.c.name,
        service_connector_table.c.user_id,
    )

    connection = op.get_bind()
    names = set()
    for id, name, user_id in connection.execute(query).fetchall():
        if name in names:
            name = f"{name}-{user_id}"
            # This will never happen, as we had a constraint on unique names
            # per user
            assert name not in names
            connection.execute(
                sa.update(service_connector_table)
                .where(service_connector_table.c.id == id)
                .values(name=name)
            )

        names.add(name)


def upgrade() -> None:
    """Upgrade database schema and/or data, creating a new revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    resolve_duplicate_names()

    with op.batch_alter_table("service_connector", schema=None) as batch_op:
        batch_op.drop_column("is_shared")

    with op.batch_alter_table("stack", schema=None) as batch_op:
        batch_op.drop_column("is_shared")

    with op.batch_alter_table("stack_component", schema=None) as batch_op:
        batch_op.drop_column("is_shared")

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade database schema and/or data back to the previous revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("stack_component", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_shared", sa.BOOLEAN(), nullable=False)
        )

    with op.batch_alter_table("stack", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_shared", sa.BOOLEAN(), nullable=False)
        )

    with op.batch_alter_table("service_connector", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_shared", sa.BOOLEAN(), nullable=False)
        )
    # ### end Alembic commands ###
