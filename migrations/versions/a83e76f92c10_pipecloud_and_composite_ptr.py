"""pipecloud_and_composite_ptr

Revision ID: a83e76f92c10
Revises: 65bdade8759d
Create Date: 2026-08-20 14:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a83e76f92c10'
down_revision: Union[str, None] = '65bdade8759d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    # 1. Add PipeCloud & archive columns to pressure_tests if exists
    if 'pressure_tests' in tables:
        cols = [c['name'] for c in insp.get_columns('pressure_tests')]
        with op.batch_alter_table('pressure_tests', schema=None) as batch_op:
            if 'pipecloud_added' not in cols:
                batch_op.add_column(sa.Column('pipecloud_added', sa.Boolean(), server_default='0', nullable=False))
            if 'pipecloud_updated_at' not in cols:
                batch_op.add_column(sa.Column('pipecloud_updated_at', sa.DateTime(timezone=True), nullable=True))
            if 'pipecloud_updated_by_user_id' not in cols:
                batch_op.add_column(sa.Column('pipecloud_updated_by_user_id', sa.String(length=36), nullable=True))
            if 'pipecloud_updated_by_name' not in cols:
                batch_op.add_column(sa.Column('pipecloud_updated_by_name', sa.String(length=128), nullable=True))
            if 'is_archived' not in cols:
                batch_op.add_column(sa.Column('is_archived', sa.Boolean(), server_default='0', nullable=False))

    # 2. Create pressure_test_records if not exists
    if 'pressure_test_records' not in tables:
        op.create_table(
            'pressure_test_records',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('record_number', sa.String(length=64), nullable=False),
            sa.Column('project', sa.String(length=128), nullable=False),
            sa.Column('system', sa.String(length=128), nullable=False),
            sa.Column('ins_no', sa.String(length=64), nullable=True),
            sa.Column('test_date', sa.String(length=32), nullable=True),
            sa.Column('test_medium', sa.String(length=64), nullable=True),
            sa.Column('design_pressure', sa.String(length=64), nullable=True),
            sa.Column('test_pressure', sa.String(length=64), nullable=True),
            sa.Column('duration_min', sa.String(length=32), nullable=True),
            sa.Column('status', sa.String(length=32), nullable=False),
            sa.Column('foreman_name', sa.String(length=128), nullable=True),
            sa.Column('qc_inspector', sa.String(length=128), nullable=True),
            sa.Column('client_surveyor', sa.String(length=128), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('verification_code', sa.String(length=64), nullable=True),
            sa.Column('confirmed_by_user_id', sa.String(length=36), nullable=True),
            sa.Column('confirmed_by_name', sa.String(length=128), nullable=True),
            sa.Column('confirmed_by_role', sa.String(length=64), nullable=True),
            sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('signature_image_path', sa.String(length=255), nullable=True),
            sa.Column('signed_copy_path', sa.String(length=255), nullable=True),
            sa.Column('sha256_hash', sa.String(length=64), nullable=True),
            sa.Column('official_pdf_sha256', sa.String(length=64), nullable=True),
            sa.Column('full_pdf_sha256', sa.String(length=64), nullable=True),
            sa.Column('snapshot_json', sa.JSON(), nullable=False),
            sa.Column('is_archived', sa.Boolean(), server_default='0', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_pressure_test_records_record_number'), 'pressure_test_records', ['record_number'], unique=True)
        op.create_index(op.f('ix_pressure_test_records_verification_code'), 'pressure_test_records', ['verification_code'], unique=False)
        op.create_index(op.f('ix_pressure_test_records_is_archived'), 'pressure_test_records', ['is_archived'], unique=False)

    # 3. Create pressure_test_record_logs
    if 'pressure_test_record_logs' not in tables:
        op.create_table(
            'pressure_test_record_logs',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('record_id', sa.String(length=36), nullable=False),
            sa.Column('pressure_test_id', sa.String(length=36), nullable=False),
            sa.Column('test_revision_id', sa.String(length=36), nullable=False),
            sa.Column('position', sa.Integer(), nullable=False),
            sa.Column('include_measurement_table', sa.Boolean(), server_default='1', nullable=False),
            sa.Column('selected_pipe_numbers', sa.JSON(), nullable=False),
            sa.Column('metadata_snapshot', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['pressure_test_id'], ['pressure_tests.id'], ),
            sa.ForeignKeyConstraint(['record_id'], ['pressure_test_records.id'], ),
            sa.ForeignKeyConstraint(['test_revision_id'], ['test_revisions.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_pressure_test_record_logs_record_id'), 'pressure_test_record_logs', ['record_id'], unique=False)
        op.create_index(op.f('ix_pressure_test_record_logs_pressure_test_id'), 'pressure_test_record_logs', ['pressure_test_id'], unique=False)

    # 4. Create pressure_test_record_log_artifacts
    if 'pressure_test_record_log_artifacts' not in tables:
        op.create_table(
            'pressure_test_record_log_artifacts',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('record_log_id', sa.String(length=36), nullable=False),
            sa.Column('artifact_id', sa.String(length=36), nullable=True),
            sa.Column('source', sa.String(length=32), nullable=False),
            sa.Column('category', sa.String(length=32), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('storage_key', sa.String(length=512), nullable=False),
            sa.Column('sha256', sa.String(length=64), nullable=False),
            sa.Column('position', sa.Integer(), nullable=False),
            sa.Column('is_included_in_pdf', sa.Boolean(), server_default='1', nullable=False),
            sa.Column('created_by_name', sa.String(length=128), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id'], ),
            sa.ForeignKeyConstraint(['record_log_id'], ['pressure_test_record_logs.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_pressure_test_record_log_artifacts_record_log_id'), 'pressure_test_record_log_artifacts', ['record_log_id'], unique=False)

    # 5. Create pressure_test_record_items
    if 'pressure_test_record_items' not in tables:
        op.create_table(
            'pressure_test_record_items',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('record_id', sa.String(length=36), nullable=False),
            sa.Column('record_log_id', sa.String(length=36), nullable=True),
            sa.Column('item_no', sa.Integer(), nullable=False),
            sa.Column('pipe_number', sa.String(length=64), nullable=False),
            sa.Column('drawing_no', sa.String(length=128), nullable=True),
            sa.Column('spool_no', sa.String(length=128), nullable=True),
            sa.Column('log_no', sa.String(length=64), nullable=True),
            sa.Column('hold_start_bar', sa.String(length=32), nullable=True),
            sa.Column('hold_end_bar', sa.String(length=32), nullable=True),
            sa.Column('result', sa.String(length=16), nullable=False),
            sa.Column('notes', sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(['record_id'], ['pressure_test_records.id'], ),
            sa.ForeignKeyConstraint(['record_log_id'], ['pressure_test_record_logs.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_pressure_test_record_items_record_id'), 'pressure_test_record_items', ['record_id'], unique=False)


def downgrade() -> None:
    op.drop_table('pressure_test_record_items')
    op.drop_table('pressure_test_record_log_artifacts')
    op.drop_table('pressure_test_record_logs')
    op.drop_table('pressure_test_records')
    with op.batch_alter_table('pressure_tests', schema=None) as batch_op:
        batch_op.drop_column('is_archived')
        batch_op.drop_column('pipecloud_updated_by_name')
        batch_op.drop_column('pipecloud_updated_by_user_id')
        batch_op.drop_column('pipecloud_updated_at')
        batch_op.drop_column('pipecloud_added')
