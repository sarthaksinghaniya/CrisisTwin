"""create_grievance_tables

Revision ID: f23554c872aa
Revises: 
Create Date: 2026-06-20 02:43:52.643248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f23554c872aa'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    existing_enums = []
    if bind.engine.name == 'postgresql':
        existing_enums = [
            row[0] for row in bind.execute(
                sa.text("SELECT typname FROM pg_type WHERE typtype = 'e';")
            ).all()
        ]

    # Handle RoleEnum dynamically based on existence
    role_enum_create = 'roleenum' not in existing_enums
    role_enum = sa.Enum('CITIZEN', 'OFFICER', 'HEAD', 'ADMIN', name='roleenum', create_type=role_enum_create)

    # Handle PriorityEnum dynamically based on existence
    priority_enum_create = 'priorityenum' not in existing_enums
    priority_enum = sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='priorityenum', create_type=priority_enum_create)

    # Handle ComplaintStatus enum dynamically based on existence
    status_enum_create = 'complaintstatus' not in existing_enums
    status_enum = sa.Enum('OPEN', 'IN_PROGRESS', 'RESOLVED', 'REJECTED', 'ESCALATED', name='complaintstatus', create_type=status_enum_create)

    # 1. otps table
    if 'otps' not in existing_tables:
        op.create_table('otps',
            sa.Column('email', sa.String(length=150), nullable=False),
            sa.Column('otp_hash', sa.String(), nullable=False),
            sa.Column('expiry', sa.DateTime(timezone=True), nullable=False),
            sa.Column('attempts', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint('email')
        )
        op.create_index(op.f('ix_otps_email'), 'otps', ['email'], unique=False)

    # 2. users table
    if 'users' not in existing_tables:
        op.create_table('users',
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('email', sa.String(length=150), nullable=False),
            sa.Column('phone', sa.String(length=15), nullable=True),
            sa.Column('password', sa.String(), nullable=True),
            sa.Column('role', role_enum, nullable=False),
            sa.Column('department', sa.String(length=100), nullable=True),
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_deleted', sa.Boolean(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
        op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)

    # 3. complaints table
    if 'complaints' not in existing_tables:
        op.create_table('complaints',
            sa.Column('ticket_id', sa.String(length=20), nullable=False),
            sa.Column('citizen_name', sa.String(length=100), nullable=True),
            sa.Column('citizen_email', sa.String(length=150), nullable=True),
            sa.Column('citizen_phone', sa.String(length=15), nullable=True),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('category', sa.String(length=100), nullable=False),
            sa.Column('department', sa.String(length=100), nullable=False),
            sa.Column('district', sa.String(length=100), nullable=False),
            sa.Column('lat', sa.Float(), nullable=True),
            sa.Column('lon', sa.Float(), nullable=True),
            sa.Column('priority', priority_enum, nullable=False),
            sa.Column('status', status_enum, nullable=False),
            sa.Column('assigned_to', sa.Integer(), nullable=True),
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_deleted', sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(['assigned_to'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_complaints_assigned_to'), 'complaints', ['assigned_to'], unique=False)
        op.create_index(op.f('ix_complaints_category'), 'complaints', ['category'], unique=False)
        op.create_index(op.f('ix_complaints_district'), 'complaints', ['district'], unique=False)
        op.create_index(op.f('ix_complaints_id'), 'complaints', ['id'], unique=False)
        op.create_index(op.f('ix_complaints_priority'), 'complaints', ['priority'], unique=False)
        op.create_index(op.f('ix_complaints_status'), 'complaints', ['status'], unique=False)
        op.create_index(op.f('ix_complaints_ticket_id'), 'complaints', ['ticket_id'], unique=True)

    # 4. notifications table
    if 'notifications' not in existing_tables:
        op.create_table('notifications',
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('is_read', sa.Boolean(), nullable=False),
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_deleted', sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_notifications_id'), 'notifications', ['id'], unique=False)

    # 5. attachments table
    if 'attachments' not in existing_tables:
        op.create_table('attachments',
            sa.Column('complaint_id', sa.Integer(), nullable=False),
            sa.Column('file_url', sa.String(), nullable=False),
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_deleted', sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_attachments_id'), 'attachments', ['id'], unique=False)

    # 6. comments table
    if 'comments' not in existing_tables:
        op.create_table('comments',
            sa.Column('complaint_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_deleted', sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_comments_id'), 'comments', ['id'], unique=False)

    # 7. complaint_updates table
    if 'complaint_updates' not in existing_tables:
        op.create_table('complaint_updates',
            sa.Column('complaint_id', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('updated_by', sa.Integer(), nullable=True),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_deleted', sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_complaint_updates_id'), 'complaint_updates', ['id'], unique=False)

    # 8. escalations table
    if 'escalations' not in existing_tables:
        op.create_table('escalations',
            sa.Column('complaint_id', sa.Integer(), nullable=False),
            sa.Column('escalated_by', sa.Integer(), nullable=True),
            sa.Column('escalated_to', sa.Integer(), nullable=True),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_deleted', sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['escalated_by'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['escalated_to'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_escalations_id'), 'escalations', ['id'], unique=False)

    # 9. feedbacks table
    if 'feedbacks' not in existing_tables:
        op.create_table('feedbacks',
            sa.Column('complaint_id', sa.Integer(), nullable=False),
            sa.Column('citizen_id', sa.Integer(), nullable=True),
            sa.Column('rating', sa.Integer(), nullable=False),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_deleted', sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(['citizen_id'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_feedbacks_id'), 'feedbacks', ['id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # Drop tables in safe cascade order (dependents first)
    if 'feedbacks' in existing_tables:
        op.drop_index(op.f('ix_feedbacks_id'), table_name='feedbacks')
        op.drop_table('feedbacks')
        
    if 'escalations' in existing_tables:
        op.drop_index(op.f('ix_escalations_id'), table_name='escalations')
        op.drop_table('escalations')
        
    if 'complaint_updates' in existing_tables:
        op.drop_index(op.f('ix_complaint_updates_id'), table_name='complaint_updates')
        op.drop_table('complaint_updates')
        
    if 'comments' in existing_tables:
        op.drop_index(op.f('ix_comments_id'), table_name='comments')
        op.drop_table('comments')
        
    if 'attachments' in existing_tables:
        op.drop_index(op.f('ix_attachments_id'), table_name='attachments')
        op.drop_table('attachments')
        
    if 'notifications' in existing_tables:
        op.drop_index(op.f('ix_notifications_id'), table_name='notifications')
        op.drop_table('notifications')
        
    if 'complaints' in existing_tables:
        op.drop_index(op.f('ix_complaints_ticket_id'), table_name='complaints')
        op.drop_index(op.f('ix_complaints_status'), table_name='complaints')
        op.drop_index(op.f('ix_complaints_priority'), table_name='complaints')
        op.drop_index(op.f('ix_complaints_id'), table_name='complaints')
        op.drop_index(op.f('ix_complaints_district'), table_name='complaints')
        op.drop_index(op.f('ix_complaints_category'), table_name='complaints')
        op.drop_index(op.f('ix_complaints_assigned_to'), table_name='complaints')
        op.drop_table('complaints')
        
    if 'users' in existing_tables:
        op.drop_index(op.f('ix_users_id'), table_name='users')
        op.drop_index(op.f('ix_users_email'), table_name='users')
        op.drop_table('users')
        
    if 'otps' in existing_tables:
        op.drop_index(op.f('ix_otps_email'), table_name='otps')
        op.drop_table('otps')

    # Drop enums if they exist in Postgres
    if bind.engine.name == 'postgresql':
        existing_enums = [
            row[0] for row in bind.execute(
                sa.text("SELECT typname FROM pg_type WHERE typtype = 'e';")
            ).all()
        ]
        
        if 'roleenum' in existing_enums:
            bind.execute(sa.text("DROP TYPE roleenum;"))
        if 'priorityenum' in existing_enums:
            bind.execute(sa.text("DROP TYPE priorityenum;"))
        if 'complaintstatus' in existing_enums:
            bind.execute(sa.text("DROP TYPE complaintstatus;"))
