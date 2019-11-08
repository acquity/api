"""Add friendly name to chat room

Revision ID: 72565d05787b
Revises: 441896589af1
Create Date: 2019-11-08 15:18:26.777623

"""
import sqlalchemy as sa

from alembic import op
from src.database import ChatRoom
from src.utils import generate_friendly_name

# revision identifiers, used by Alembic.
revision = "72565d05787b"
down_revision = "441896589af1"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("chat_rooms", sa.Column("friendly_name", sa.String(), nullable=True))

    bind = op.get_bind()
    session = sa.orm.Session(bind=bind)
    for chat_room in session.query(ChatRoom).all():
        chat_room.friendly_name = generate_friendly_name()
    session.commit()

    op.alter_column("chat_rooms", "friendly_name", nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("chat_rooms", "friendly_name")
    # ### end Alembic commands ###