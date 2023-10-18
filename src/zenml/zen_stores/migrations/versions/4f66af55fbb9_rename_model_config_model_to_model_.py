"""rename model_config_model to model_config in pipeline and step configs [4f66af55fbb9].

Revision ID: 4f66af55fbb9
Revises: 0.45.2
Create Date: 2023-10-17 13:57:35.810054

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = "4f66af55fbb9"
down_revision = "0.45.2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema and/or data, creating a new revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        table_name="model",
        column_name="ethic",
        new_column_name="ethics",
        existing_type=sa.TEXT(),
    )

    connection = op.get_bind()

    update_config_fields = text(
        """
        UPDATE pipeline_deployment
        SET pipeline_configuration = REPLACE(
            pipeline_configuration,
            '"model_config_model"',
            '"model_config"'
        ),
        step_configurations = REPLACE(
            step_configurations,
            '"model_config_model"',
            '"model_config"'
        )
        """
    )
    connection.execute(update_config_fields)

    update_config_fields = text(
        """
        UPDATE step_run
        SET step_configuration = REPLACE(
            step_configuration,
            '"model_config_model"',
            '"model_config"'
        )
        """
    )
    connection.execute(update_config_fields)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade database schema and/or data back to the previous revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        table_name="model",
        column_name="ethics",
        new_column_name="ethic",
        existing_type=sa.TEXT(),
    )

    connection = op.get_bind()

    update_config_fields = text(
        """
        UPDATE pipeline_deployment
        SET pipeline_configuration = REPLACE(
            pipeline_configuration,
            '"model_config"',
            '"model_config_model"'
        ),
        step_configurations = REPLACE(
            step_configurations,
            '"model_config"',
            '"model_config_model"'
        )
        """
    )
    connection.execute(update_config_fields)

    update_config_fields = text(
        """
        UPDATE step_run
        SET step_configuration = REPLACE(
            step_configuration,
            '"model_config"',
            '"model_config_model"'
        )
        """
    )
    connection.execute(update_config_fields)

    # ### end Alembic commands ###
