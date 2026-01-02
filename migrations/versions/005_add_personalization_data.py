"""Add personalization_data field to users table

Revision ID: 005_add_personalization_data
Revises: 004_add_consultation_used
Create Date: 2025-12-28 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '005_add_personalization_data'
down_revision: Union[str, None] = '004_add_consultation_used'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Получаем список существующих колонок
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    # Добавляем поле personalization_data в таблицу users (если еще не существует)
    if 'personalization_data' not in columns:
        op.add_column('users', sa.Column('personalization_data', postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    # Получаем список существующих колонок
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    # Удаляем поле personalization_data из таблицы users
    if 'personalization_data' in columns:
        op.drop_column('users', 'personalization_data')

