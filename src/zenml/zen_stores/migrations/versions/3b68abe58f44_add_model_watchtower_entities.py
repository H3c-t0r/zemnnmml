"""add Model Control Plane entities [3b68abe58f44].

Revision ID: 3b68abe58f44
Revises: 37835ce041d2
Create Date: 2023-09-11 07:53:18.641081

"""
import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "3b68abe58f44"
down_revision = "37835ce041d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema and/or data, creating a new revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "model",
        sa.Column(
            "workspace_id", sqlmodel.sql.sqltypes.GUID(), nullable=False
        ),
        sa.Column("user_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
        sa.Column("license", sa.TEXT(), nullable=True),
        sa.Column("description", sa.TEXT(), nullable=True),
        sa.Column("audience", sa.TEXT(), nullable=True),
        sa.Column("use_cases", sa.TEXT(), nullable=True),
        sa.Column("limitations", sa.TEXT(), nullable=True),
        sa.Column("trade_offs", sa.TEXT(), nullable=True),
        sa.Column("ethic", sa.TEXT(), nullable=True),
        sa.Column("tags", sa.TEXT(), nullable=True),
        sa.Column("id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("updated", sa.DateTime(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_model_user_id_user",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspace.id"],
            name="fk_model_workspace_id_workspace",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "model_version",
        sa.Column(
            "workspace_id", sqlmodel.sql.sqltypes.GUID(), nullable=False
        ),
        sa.Column("user_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
        sa.Column("model_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("number", sa.INTEGER(), nullable=False),
        sa.Column("description", sa.TEXT(), nullable=True),
        sa.Column("stage", sa.TEXT(), nullable=True),
        sa.Column("id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("updated", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["model.id"],
            name="fk_model_version_model_id_model",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_model_version_user_id_user",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspace.id"],
            name="fk_model_version_workspace_id_workspace",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "model_versions_artifacts",
        sa.Column(
            "workspace_id", sqlmodel.sql.sqltypes.GUID(), nullable=False
        ),
        sa.Column("user_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
        sa.Column("model_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column(
            "model_version_id", sqlmodel.sql.sqltypes.GUID(), nullable=False
        ),
        sa.Column("artifact_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
        sa.Column("is_model_object", sa.BOOLEAN(), nullable=True),
        sa.Column("is_deployment", sa.BOOLEAN(), nullable=True),
        sa.Column("id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("updated", sa.DateTime(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "pipeline_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "step_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("version", sa.INTEGER(), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifact.id"],
            name="fk_model_versions_artifacts_artifact_id_artifact",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["model.id"],
            name="fk_model_versions_artifacts_model_id_model",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_version.id"],
            name="fk_model_versions_artifacts_model_version_id_model_version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_model_versions_artifacts_user_id_user",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspace.id"],
            name="fk_model_versions_artifacts_workspace_id_workspace",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "model_versions_runs",
        sa.Column(
            "workspace_id", sqlmodel.sql.sqltypes.GUID(), nullable=False
        ),
        sa.Column("user_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
        sa.Column("model_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column(
            "model_version_id", sqlmodel.sql.sqltypes.GUID(), nullable=False
        ),
        sa.Column(
            "pipeline_run_id", sqlmodel.sql.sqltypes.GUID(), nullable=True
        ),
        sa.Column("id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("updated", sa.DateTime(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["model.id"],
            name="fk_model_versions_runs_model_id_model",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_version.id"],
            name="fk_model_versions_runs_model_version_id_model_version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_run.id"],
            name="fk_model_versions_runs_run_id_pipeline_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_model_versions_runs_user_id_user",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspace.id"],
            name="fk_model_versions_runs_workspace_id_workspace",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade database schema and/or data back to the previous revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("model")
    op.drop_table("model_versions_runs")
    op.drop_table("model_versions_artifacts")
    op.drop_table("model_version")
    # ### end Alembic commands ###
