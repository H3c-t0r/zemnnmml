"""make is_service_account mandatory [722392c91006].

Revision ID: 722392c91006
Revises: 0.46.1
Create Date: 2023-11-13 15:38:26.253610

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = "722392c91006"
down_revision = "0.46.1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema and/or data, creating a new revision."""
    # ### commands auto generated by Alembic - please adjust! ###

    connection = op.get_bind()

    # Get all users where `is_service_account` is null
    get_null_is_service_account = text(
        """
        SELECT id, name
        FROM user
        WHERE is_service_account IS NULL
        """
    )
    result = connection.execute(get_null_is_service_account)

    # For each user, if another user with the same name exists and has
    # `is_service_account` set to false, rename it and its default stack
    for row in result:
        id, name = row
        get_other_user = text(
            """
            SELECT id
            FROM user
            WHERE name = :name
            AND id != :id
            AND is_service_account = 0
            """
        )
        other_user_result = connection.execute(
            get_other_user, {"name": name, "id": id}
        )
        for other_user_row in other_user_result:
            new_name = f"{name}-{id[:4]}"
            other_user_id = other_user_row[0]
            description = (
                "This default user was renamed during migration. Please use "
                "the `default` user instead and delete this user when no "
                "longer needed."
            )
            update_other_user = text(
                """
                UPDATE user
                SET name = :new_name, full_name = :full_name
                WHERE id = :id
                """
            )
            connection.execute(
                update_other_user,
                {
                    "new_name": new_name,
                    "id": other_user_id,
                    "full_name": description,
                },
            )
            update_default_stack = text(
                """
                UPDATE stack
                SET name = :new_name
                WHERE user_id = :id
                AND name = 'default'
                """
            )
            connection.execute(
                update_default_stack,
                {"new_name": new_name, "id": other_user_id},
            )
            update_default_components = text(
                """
                UPDATE stack_component
                SET name = :new_name
                WHERE user_id = :other_user_id
                AND name = 'default'
                """
            )
            connection.execute(
                update_default_components,
                {"new_name": new_name, "other_user_id": id},
            )

    # Fill in `is_service_account` for all users that don't have it
    update_null_is_service_account = text(
        """
        UPDATE user
        SET is_service_account = 0
        WHERE is_service_account IS NULL
        """
    )
    connection.execute(update_null_is_service_account)
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.alter_column(
            "is_service_account", existing_type=sa.BOOLEAN(), nullable=False
        )

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade database schema and/or data back to the previous revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.alter_column(
            "is_service_account", existing_type=sa.BOOLEAN(), nullable=True
        )

    # ### end Alembic commands ###
