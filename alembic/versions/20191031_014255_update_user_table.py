"""update user table

Revision ID: a7ea1a7c565b
Revises: 593c10ebcda7
Create Date: 2019-10-31 01:42:55.074780

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "a7ea1a7c565b"
down_revision = "593c10ebcda7"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("users", sa.Column("display_image", sa.String(), nullable=True))
    op.add_column("users", sa.Column("provider", sa.String(), nullable=False))
    op.add_column("users", sa.Column("user_id", sa.String(), nullable=False))
    op.create_unique_constraint(None, "users", ["user_id"])
    op.drop_column("users", "hashed_password")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "users",
        sa.Column("hashed_password", sa.VARCHAR(), autoincrement=False, nullable=False),
    )
    op.drop_constraint(None, "users", type_="unique")
    op.drop_column("users", "user_id")
    op.drop_column("users", "provider")
    op.drop_column("users", "display_image")
    # ### end Alembic commands ###