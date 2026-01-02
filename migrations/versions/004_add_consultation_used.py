"""Add consultation_used field to users table

Revision ID: 004_add_consultation_used
Revises: 003_add_survey_state
Create Date: 2024-01-01 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_add_consultation_used'
down_revision: Union[str, None] = '003_add_survey_state'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Получаем список существующих колонок
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    # Добавляем поле consultation_used в таблицу users (если еще не существует)
    if 'consultation_used' not in columns:
        op.add_column('users', sa.Column('consultation_used', sa.Boolean(), nullable=False, server_default='false'))
        # Обновляем существующие записи - устанавливаем false для всех пользователей
        op.execute("UPDATE users SET consultation_used = false WHERE consultation_used IS NULL")


def downgrade() -> None:
    # Получаем список существующих колонок
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    # Удаляем поле consultation_used из таблицы users
    if 'consultation_used' in columns:
        op.drop_column('users', 'consultation_used')

