"""Add Caching Info [a40116f07005].

Revision ID: a40116f07005
Revises: 0.22.0
Create Date: 2022-11-21 15:24:02.436227

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a40116f07005"
down_revision = "0.22.0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema and/or data, creating a new revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("pipeline_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("enable_cache", sa.Boolean(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("start_time", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(sa.Column("end_time", sa.DateTime(), nullable=True))

    with op.batch_alter_table("step_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("caching_parameters", sa.TEXT(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("enable_cache", sa.Boolean(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("start_time", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(sa.Column("end_time", sa.DateTime(), nullable=True))

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade database schema and/or data back to the previous revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("step_run", schema=None) as batch_op:
        batch_op.drop_column("end_time")
        batch_op.drop_column("start_time")
        batch_op.drop_column("enable_cache")
        batch_op.drop_column("caching_parameters")

    with op.batch_alter_table("pipeline_run", schema=None) as batch_op:
        batch_op.drop_column("end_time")
        batch_op.drop_column("start_time")
        batch_op.drop_column("enable_cache")

    # ### end Alembic commands ###
