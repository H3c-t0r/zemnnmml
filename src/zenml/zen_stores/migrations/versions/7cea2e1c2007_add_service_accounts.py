"""add service accounts [7cea2e1c2007].

Revision ID: 7cea2e1c2007
Revises: 0.45.6
Create Date: 2023-11-03 19:30:58.523804

"""
import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "7cea2e1c2007"
down_revision = "0.45.6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema and/or data, creating a new revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "api_key",
        sa.Column(
            "service_account_id", sqlmodel.sql.sqltypes.GUID(), nullable=False
        ),
        sa.Column("id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("updated", sa.DateTime(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "description", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "previous_key", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("retain_period", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("last_rotated", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["service_account_id"],
            ["user.id"],
            name="fk_api_key_service_account_id_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_service_account", sa.Boolean(), nullable=True)
        )

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade database schema and/or data back to the previous revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("is_service_account")

    op.drop_table("api_key")
    # ### end Alembic commands ###
