"""Add new survey fields and roadmap support

Revision ID: 001_add_new_survey_fields
Revises: 
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_add_new_survey_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем новые поля в таблицу users (только если их еще нет)
    try:
        op.add_column('users', sa.Column('name', sa.String(length=255), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('users', sa.Column('gender', sa.String(length=20), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('users', sa.Column('age', sa.Integer(), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('users', sa.Column('values', postgresql.ARRAY(sa.String()), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('users', sa.Column('development_spheres', postgresql.ARRAY(sa.String()), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('users', sa.Column('goal_3months', sa.Text(), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('users', sa.Column('roadmap', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('users', sa.Column('homework_needs_revision', sa.Boolean(), nullable=False, server_default='false'))
    except Exception:
        pass
    
    # Обновляем таблицу surveys (только если колонок еще нет)
    try:
        op.add_column('surveys', sa.Column('basic_answers', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('surveys', sa.Column('detailed_answers', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('surveys', sa.Column('detailed_questions', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('surveys', sa.Column('role_model', sa.String(length=50), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('surveys', sa.Column('goal_3months', sa.Text(), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('surveys', sa.Column('roadmap', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    except Exception:
        pass
    
    # Мигрируем старые данные: если есть старое поле answers, копируем в basic_answers
    try:
        op.execute("""
            UPDATE surveys 
            SET basic_answers = answers 
            WHERE answers IS NOT NULL AND basic_answers IS NULL
        """)
    except Exception:
        # Если миграция данных не удалась, пропускаем
        pass
    
    # Старое поле answers оставляем для совместимости (не удаляем)
    
    # Обновляем таблицу reports (только если колонок еще нет)
    try:
        op.add_column('reports', sa.Column('is_approved', sa.Boolean(), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('reports', sa.Column('revision_required', sa.Boolean(), nullable=False, server_default='false'))
    except Exception:
        pass


def downgrade() -> None:
    # Удаляем новые поля из reports
    op.drop_column('reports', 'revision_required')
    op.drop_column('reports', 'is_approved')
    
    # Удаляем новые поля из surveys
    op.drop_column('surveys', 'roadmap')
    op.drop_column('surveys', 'goal_3months')
    op.drop_column('surveys', 'role_model')
    op.drop_column('surveys', 'detailed_questions')
    op.drop_column('surveys', 'detailed_answers')
    op.drop_column('surveys', 'basic_answers')
    
    # Удаляем новые поля из users
    op.drop_column('users', 'homework_needs_revision')
    op.drop_column('users', 'roadmap')
    op.drop_column('users', 'goal_3months')
    op.drop_column('users', 'development_spheres')
    op.drop_column('users', 'values')
    op.drop_column('users', 'age')
    op.drop_column('users', 'gender')
    op.drop_column('users', 'name')

