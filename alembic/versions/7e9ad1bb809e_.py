"""empty message

Revision ID: 7e9ad1bb809e
Revises: a01f82635acf
Create Date: 2023-03-01 21:23:13.505233

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '7e9ad1bb809e'
down_revision = 'a01f82635acf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user_otp',
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('secret', sa.String(), nullable=False),
    sa.Column('status', sa.Enum('AVAILABLE', 'AWAITING_VERIFICATION', name='otpstatustype'), nullable=True),
    sa.Column('hashed_recovery_codes', sa.ARRAY(sa.String()), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_otp_id'), 'user_otp', ['id'], unique=True)
    op.drop_index('ix_image_proxy_id', table_name='image_proxy')
    op.drop_table('image_proxy')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('image_proxy',
    sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
    sa.Column('id', postgresql.UUID(), autoincrement=False, nullable=False),
    sa.Column('alias_id', postgresql.UUID(), autoincrement=False, nullable=True),
    sa.Column('hashed_url', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('path', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['alias_id'], ['email_alias.id'], name='image_proxy_alias_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='image_proxy_pkey')
    )
    op.create_index('ix_image_proxy_id', 'image_proxy', ['id'], unique=False)
    op.drop_index(op.f('ix_user_otp_id'), table_name='user_otp')
    op.drop_table('user_otp')
    # ### end Alembic commands ###
