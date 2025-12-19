"""Add premium_expires_at field to users table

Revision ID: 002_add_premium_expires_at
Revises: 
Create Date: 2024-12-19 00:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_add_premium_expires_at'
down_revision = '001_add_new_survey_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поле premium_expires_at в таблицу users (если еще не существует)
    # Проверяем существование колонки перед добавлением
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'premium_expires_at' not in columns:
        op.add_column('users', sa.Column('premium_expires_at', sa.DateTime(timezone=True), nullable=True))
    
    # Добавляем поле personality если его нет
    if 'personality' not in columns:
        op.add_column('users', sa.Column('personality', sa.String(length=50), nullable=True))


def downgrade() -> None:
    # Удаляем поле premium_expires_at из таблицы users
    op.drop_column('users', 'premium_expires_at')

