"""empty message

Revision ID: 5c40410b1728
Revises: 258fe4c44670
Create Date: 2023-02-25 19:30:44.618350

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5c40410b1728'
down_revision = '258fe4c44670'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_otp_authentication_id', table_name='otp_authentication')
    op.drop_table('otp_authentication')
    op.add_column('user_otp', sa.Column('created_at', sa.DateTime(), nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user_otp', 'created_at')
    op.create_table('otp_authentication',
    sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
    sa.Column('id', postgresql.UUID(), autoincrement=False, nullable=False),
    sa.Column('user_id', postgresql.UUID(), autoincrement=False, nullable=False),
    sa.Column('tries', sa.SMALLINT(), autoincrement=False, nullable=False),
    sa.Column('hashed_cors_token', sa.VARCHAR(length=97), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='otp_authentication_user_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='otp_authentication_pkey')
    )
    op.create_index('ix_otp_authentication_id', 'otp_authentication', ['id'], unique=False)
    # ### end Alembic commands ###
