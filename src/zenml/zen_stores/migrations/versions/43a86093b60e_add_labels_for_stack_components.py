"""add labels for stack components [43a86093b60e].

Revision ID: 43a86093b60e
Revises: 0.37.0
Create Date: 2023-03-28 11:26:33.358600

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "43a86093b60e"
down_revision = "0.37.0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema and/or data, creating a new revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("stack_component", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("labels", sa.LargeBinary(), nullable=True)
        )

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade database schema and/or data back to the previous revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("stack_component", schema=None) as batch_op:
        batch_op.drop_column("labels")

    # ### end Alembic commands ###
