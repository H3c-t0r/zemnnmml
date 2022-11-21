"""Add num_outputs to run step [8a64fbfecda0].

Revision ID: 8a64fbfecda0
Revises: 5330ba58bf20
Create Date: 2022-11-08 16:20:35.241562

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "8a64fbfecda0"
down_revision = "5330ba58bf20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema and/or data, creating a new revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("pipeline_run", schema=None) as batch_op:
        batch_op.alter_column(
            "num_steps", existing_type=sa.Integer(), nullable=True
        )

    with op.batch_alter_table("step_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("num_outputs", sa.Integer(), nullable=True)
        )

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade database schema and/or data back to the previous revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("step_run", schema=None) as batch_op:
        batch_op.drop_column("num_outputs")

    with op.batch_alter_table("pipeline_run", schema=None) as batch_op:
        batch_op.alter_column(
            "num_steps", existing_type=sa.Integer(), nullable=False
        )

    # ### end Alembic commands ###
