"""PaySpotTransaction, dodata kolona order_confirmation

Revision ID: a44857ff2b83
Revises: 6bd1cd0ce702
Create Date: 2025-04-25 19:58:24.849564

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a44857ff2b83'
down_revision = '6bd1cd0ce702'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('pay_spot_transaction', schema=None) as batch_op:
        batch_op.add_column(sa.Column('order_confirmation', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('pay_spot_transaction', schema=None) as batch_op:
        batch_op.drop_column('order_confirmation')

    # ### end Alembic commands ###
