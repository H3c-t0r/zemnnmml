"""add oauth devices [f3b3964e3a0f].

Revision ID: f3b3964e3a0f
Revises: 37835ce041d2
Create Date: 2023-10-03 22:06:04.452359

"""
import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "f3b3964e3a0f"
down_revision = "3b68abe58f44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema and/or data, creating a new revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "auth_devices",
        sa.Column("user_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
        sa.Column("id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("updated", sa.DateTime(), nullable=False),
        sa.Column("client_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column(
            "user_code", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "device_code", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "status", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("failed_auth_attempts", sa.Integer(), nullable=False),
        sa.Column("expires", sa.DateTime(), nullable=True),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("trusted_device", sa.Boolean(), nullable=False),
        sa.Column("os", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "ip_address", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column(
            "hostname", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column(
            "python_version", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column(
            "zenml_version", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("city", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("region", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "country", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_auth_devices_user_id_user",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "external_user_id", sqlmodel.sql.sqltypes.GUID(), nullable=True
            )
        )

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade database schema and/or data back to the previous revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("external_user_id")

    op.drop_table("auth_devices")
    # ### end Alembic commands ###
