"""add mobile+auth models and columns

Revision ID: bd2d736d3171
Revises: db0749529a73
Create Date: 2026-07-12 20:05:33.579624

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'bd2d736d3171'
down_revision: Union[str, Sequence[str], None] = 'db0749529a73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Reused (already-existing) enum types — reference without creating.
_servicetype = postgresql.ENUM('nurse', 'technician', name='servicetype', create_type=False)
_positionsource = postgresql.ENUM('gps', 'simulated', 'manual', name='positionsource', create_type=False)
# New enum types — created explicitly in upgrade(), referenced without auto-create.
_deviceplatform = postgresql.ENUM('android', 'ios', name='deviceplatform', create_type=False)
_workerstopstatus = postgresql.ENUM(
    'pending', 'en_route', 'arrived', 'in_progress', 'completed', 'failed',
    name='workerstopstatus', create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    # create the two genuinely-new enum types up front so add_column can use them
    _deviceplatform.create(bind, checkfirst=True)
    _workerstopstatus.create(bind, checkfirst=True)

    op.create_table('worker_position_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('worker_id', sa.Integer(), nullable=False),
    sa.Column('worker_type', _servicetype, nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('lat', sa.Float(), nullable=False),
    sa.Column('lng', sa.Float(), nullable=False),
    sa.Column('h3_index', sa.String(length=20), nullable=True),
    sa.Column('accuracy_m', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('source', _positionsource, nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_worker_position_events_h3_index'), 'worker_position_events', ['h3_index'], unique=False)
    op.create_index('ix_worker_position_worker_time', 'worker_position_events', ['worker_type', 'worker_id', 'recorded_at'], unique=False)
    op.create_table('device_tokens',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('token', sa.String(length=512), nullable=False),
    sa.Column('platform', _deviceplatform, nullable=True),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.Column('last_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('employees', sa.Column('username', sa.String(length=255), nullable=True))
    op.add_column('employees', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.add_column('employees', sa.Column('unavailable_reason', sa.String(length=512), nullable=True))
    op.add_column('employees', sa.Column('status_changed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint('uq_employees_username', 'employees', ['username'])
    op.add_column('worker_assignment_stops', sa.Column('stop_status', _workerstopstatus, nullable=True))
    op.add_column('worker_assignment_stops', sa.Column('actual_service_start', sa.DateTime(timezone=True), nullable=True))
    op.add_column('worker_assignment_stops', sa.Column('actual_service_end', sa.DateTime(timezone=True), nullable=True))
    op.add_column('worker_assignment_stops', sa.Column('completion_notes', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('worker_assignment_stops', 'completion_notes')
    op.drop_column('worker_assignment_stops', 'actual_service_end')
    op.drop_column('worker_assignment_stops', 'actual_service_start')
    op.drop_column('worker_assignment_stops', 'stop_status')
    op.drop_constraint('uq_employees_username', 'employees', type_='unique')
    op.drop_column('employees', 'status_changed_at')
    op.drop_column('employees', 'unavailable_reason')
    op.drop_column('employees', 'password_hash')
    op.drop_column('employees', 'username')
    op.drop_table('device_tokens')
    op.drop_index('ix_worker_position_worker_time', table_name='worker_position_events')
    op.drop_index(op.f('ix_worker_position_events_h3_index'), table_name='worker_position_events')
    op.drop_table('worker_position_events')
    # drop the two new enum types (servicetype/positionsource are reused — keep)
    bind = op.get_bind()
    _workerstopstatus.drop(bind, checkfirst=True)
    _deviceplatform.drop(bind, checkfirst=True)
