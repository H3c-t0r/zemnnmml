"""add service accounts [93cbda80a732].

Revision ID: 93cbda80a732
Revises: 0.46.0
Create Date: 2023-11-07 13:40:23.196325

"""
import sqlmodel
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '93cbda80a732'
down_revision = '0.46.0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema and/or data, creating a new revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('api_key',
    sa.Column('description', sa.TEXT(), nullable=True),
    sa.Column('service_account_id', sqlmodel.sql.sqltypes.GUID(), nullable=False),
    sa.Column('id', sqlmodel.sql.sqltypes.GUID(), nullable=False),
    sa.Column('created', sa.DateTime(), nullable=False),
    sa.Column('updated', sa.DateTime(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('previous_key', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('retain_period', sa.Integer(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('last_login', sa.DateTime(), nullable=True),
    sa.Column('last_rotated', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['service_account_id'], ['user.id'], name='fk_api_key_service_account_id_user', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.TEXT(), nullable=True))
        batch_op.add_column(sa.Column('is_service_account', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade database schema and/or data back to the previous revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('is_service_account')
        batch_op.drop_column('description')

    op.drop_table('api_key')
    # ### end Alembic commands ###
