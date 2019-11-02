"""update offer

Revision ID: 949af0f151f9
Revises: 65b3c639b08c
Create Date: 2019-11-02 17:07:12.949929

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '949af0f151f9'
down_revision = '65b3c639b08c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('offers', sa.Column('is_buyer_agreeable', sa.Boolean(), server_default='f', nullable=False))
    op.add_column('offers', sa.Column('is_seller_agreeable', sa.Boolean(), server_default='f', nullable=False))
    op.drop_column('offers', 'is_accepted')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('offers', sa.Column('is_accepted', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False))
    op.drop_column('offers', 'is_seller_agreeable')
    op.drop_column('offers', 'is_buyer_agreeable')
    # ### end Alembic commands ###
