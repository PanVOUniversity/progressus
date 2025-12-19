"""Add survey_state field to users table

Revision ID: 003_add_survey_state
Revises: 002_add_premium_expires_at
Create Date: 2025-01-XX XX:XX:XX.XXXXXX

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_add_survey_state'
down_revision: Union[str, None] = '002_add_premium_expires_at'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем поле survey_state для сохранения состояния опроса
    # Проверяем существование колонки перед добавлением
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'survey_state' not in columns:
        op.add_column('users', sa.Column('survey_state', postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    # Удаляем поле survey_state
    try:
        op.drop_column('users', 'survey_state')
    except Exception:
        # Поле не существует, пропускаем
        pass

