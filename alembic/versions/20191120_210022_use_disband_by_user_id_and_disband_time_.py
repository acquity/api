"""Use disband_by_user_id and disband_time instead

Revision ID: 0e381789f24e
Revises: 3c017b2a1c6e
Create Date: 2019-11-20 21:00:22.476283

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0e381789f24e"
down_revision = "3c017b2a1c6e"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "chat_rooms", sa.Column("disband_by_user_id", postgresql.UUID(), nullable=True)
    )
    op.add_column("chat_rooms", sa.Column("disband_time", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        None, "chat_rooms", "users", ["disband_by_user_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_column("chat_rooms", "is_disbanded")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "chat_rooms",
        sa.Column(
            "is_disbanded",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.drop_constraint(None, "chat_rooms", type_="foreignkey")
    op.drop_column("chat_rooms", "disband_time")
    op.drop_column("chat_rooms", "disband_by_user_id")
    # ### end Alembic commands ###
