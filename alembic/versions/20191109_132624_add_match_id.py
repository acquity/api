"""add match_id

Revision ID: d2d5e6787059
Revises: c28db80d2ddb
Create Date: 2019-11-09 13:26:24.836255

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from src.database import BuyOrder, ChatRoom, Match, SellOrder

# revision identifiers, used by Alembic.
revision = "d2d5e6787059"
down_revision = "c28db80d2ddb"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("chat_rooms", sa.Column("match_id", postgresql.UUID(), nullable=True))
    bind = op.get_bind()
    session = sa.orm.Session(bind=bind)
    matches = session.query(Match).all()
    matches = (
        session.query(Match, BuyOrder, SellOrder)
        .outerjoin(BuyOrder, Match.buy_order_id == BuyOrder.id)
        .outerjoin(SellOrder, Match.sell_order_id == SellOrder.id)
        .all()
    )
    for match in matches:
        match_id = match[0].id
        buyer_id = match[1].user_id
        seller_id = match[2].user_id
        chat_room = (
            session.query(ChatRoom)
            .filter_by(buyer_id=str(buyer_id), seller_id=str(seller_id))
            .one()
        )
        chat_room.match_id = str(match_id)
    session.commit()
    op.alter_column("chat_rooms", "match_id", nullable=False)
    op.create_foreign_key(
        u"chat_room_match_id-match_id", "chat_rooms", "matches", ["match_id"], ["id"]
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(u"chat_room_match_id-match_id", "chat_rooms", type_="foreignkey")
    op.drop_column("chat_rooms", "match_id")
    # ### end Alembic commands ###