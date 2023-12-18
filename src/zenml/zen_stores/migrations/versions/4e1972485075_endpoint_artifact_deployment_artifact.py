"""endpoint_artifact>deployment_artifact [4e1972485075].

Revision ID: 4e1972485075
Revises: 0.52.0
Create Date: 2023-12-12 10:51:44.177810

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4e1972485075"
down_revision = "0.52.0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema and/or data, creating a new revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        table_name="model_versions_artifacts",
        column_name="is_endpoint_artifact",
        new_column_name="is_deployment_artifact",
        existing_type=sa.BOOLEAN(),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade database schema and/or data back to the previous revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        table_name="model_versions_artifacts",
        column_name="is_deployment_artifact",
        new_column_name="is_endpoint_artifact",
        existing_type=sa.BOOLEAN(),
    )
    # ### end Alembic commands ###
