"""Add Figma integration tables

Revision ID: 20250423_figma_001
Revises: 
Create Date: 2024-11-23

This migration adds three tables to support Figma integration:
1. figma_installation - Stores Figma installation metadata (PAT stored in Secret Manager)
2. figma_installation_access - Access control for sharing installations
3. figma_attachment - Lightweight frame URL attachments to projects
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = '20250423_figma_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create Figma integration tables.
    
    NOTE: This migration assumes the existence of the following tables:
    - users (for user_id foreign keys)
    - teams (for team_id foreign keys)
    - projects (for project_id foreign keys)
    - tech_specs (for tech_spec_id foreign keys)
    """
    
    # Create figma_installation table
    op.create_table(
        'figma_installation',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Primary key for figma_installation table'),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='Owner of the Figma installation, references users.id'),
        sa.Column('team_id', sa.BigInteger(), nullable=True, comment='Optional team association, references teams.id'),
        sa.Column('name', sa.String(length=255), nullable=False, comment='Human-readable name for the Figma installation'),
        sa.Column('description', sa.Text(), nullable=True, comment='Optional detailed description of the installation purpose'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active', comment='PAT validity state: active, expired, or disabled'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), comment='Timestamp when the installation was created'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), comment='Timestamp when the installation was last updated'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True, comment='Soft delete timestamp, NULL if installation is active'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='Stores Figma integration installations with metadata. PAT stored separately in Google Secret Manager.'
    )
    
    # Create indexes for figma_installation
    op.create_index(
        'idx_figma_installation_user',
        'figma_installation',
        ['user_id'],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL")
    )
    op.create_index(
        'idx_figma_installation_team',
        'figma_installation',
        ['team_id'],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL")
    )
    op.create_index(
        'idx_figma_installation_deleted',
        'figma_installation',
        ['deleted_at'],
        unique=False
    )
    op.create_index(
        'idx_figma_installation_status',
        'figma_installation',
        ['status'],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL")
    )
    
    # Create figma_installation_access table
    op.create_table(
        'figma_installation_access',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Primary key for figma_installation_access table'),
        sa.Column('figma_installation_id', sa.BigInteger(), nullable=False, comment='References the Figma installation being shared'),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='User who has been granted access to the installation'),
        sa.Column('granted_by', sa.BigInteger(), nullable=False, comment='User who granted this access (ADMIN or SUPER_ADMIN)'),
        sa.Column('access_level', sa.String(length=50), nullable=False, server_default='viewer', comment='Level of access: viewer, editor, or admin'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), comment='Timestamp when access was granted'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), comment='Timestamp when access record was last updated'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True, comment='Soft delete timestamp, NULL if access is active'),
        sa.ForeignKeyConstraint(['figma_installation_id'], ['figma_installation.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['granted_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('figma_installation_id', 'user_id', 'deleted_at', name='uq_figma_access_installation_user_deleted'),
        comment='Access control for sharing Figma installations between users'
    )
    
    # Create indexes for figma_installation_access
    op.create_index(
        'idx_figma_access_installation',
        'figma_installation_access',
        ['figma_installation_id'],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL")
    )
    op.create_index(
        'idx_figma_access_user',
        'figma_installation_access',
        ['user_id'],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL")
    )
    op.create_index(
        'idx_figma_access_deleted',
        'figma_installation_access',
        ['deleted_at'],
        unique=False
    )
    
    # Create figma_attachment table
    op.create_table(
        'figma_attachment',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Primary key for figma_attachment table'),
        sa.Column('project_id', sa.BigInteger(), nullable=False, comment='Project this frame is attached to'),
        sa.Column('tech_spec_id', sa.BigInteger(), nullable=True, comment='Optional technical specification association'),
        sa.Column('figma_installation_id', sa.BigInteger(), nullable=False, comment='Figma installation used to validate and access this frame'),
        sa.Column('created_by', sa.BigInteger(), nullable=False, comment='User who attached this frame'),
        sa.Column('frame_url', sa.Text(), nullable=False, comment='Full Figma frame URL'),
        sa.Column('frame_title', sa.String(length=500), nullable=True, comment='Frame title retrieved from Figma API during validation'),
        sa.Column('description', sa.Text(), nullable=True, comment='Optional user-provided description of frame purpose'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), comment='Timestamp when frame was attached'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), comment='Timestamp when attachment was last updated'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True, comment='Soft delete timestamp, NULL if attachment is active'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['figma_installation_id'], ['figma_installation.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tech_spec_id'], ['tech_specs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'frame_url', 'deleted_at', name='uq_figma_attachment_project_url_deleted'),
        comment='Lightweight storage for Figma frame URLs attached to projects. No file downloads - URLs and metadata only.'
    )
    
    # Create indexes for figma_attachment
    op.create_index(
        'idx_figma_attachment_project',
        'figma_attachment',
        ['project_id'],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL")
    )
    op.create_index(
        'idx_figma_attachment_techspec',
        'figma_attachment',
        ['tech_spec_id'],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL")
    )
    op.create_index(
        'idx_figma_attachment_installation',
        'figma_attachment',
        ['figma_installation_id'],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL")
    )
    op.create_index(
        'idx_figma_attachment_deleted',
        'figma_attachment',
        ['deleted_at'],
        unique=False
    )
    op.create_index(
        'idx_figma_attachment_project_techspec',
        'figma_attachment',
        ['project_id', 'tech_spec_id'],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL")
    )


def downgrade() -> None:
    """
    Drop Figma integration tables in reverse order to respect foreign key constraints.
    """
    # Drop figma_attachment table and its indexes
    op.drop_index('idx_figma_attachment_project_techspec', table_name='figma_attachment')
    op.drop_index('idx_figma_attachment_deleted', table_name='figma_attachment')
    op.drop_index('idx_figma_attachment_installation', table_name='figma_attachment')
    op.drop_index('idx_figma_attachment_techspec', table_name='figma_attachment')
    op.drop_index('idx_figma_attachment_project', table_name='figma_attachment')
    op.drop_table('figma_attachment')
    
    # Drop figma_installation_access table and its indexes
    op.drop_index('idx_figma_access_deleted', table_name='figma_installation_access')
    op.drop_index('idx_figma_access_user', table_name='figma_installation_access')
    op.drop_index('idx_figma_access_installation', table_name='figma_installation_access')
    op.drop_table('figma_installation_access')
    
    # Drop figma_installation table and its indexes
    op.drop_index('idx_figma_installation_status', table_name='figma_installation')
    op.drop_index('idx_figma_installation_deleted', table_name='figma_installation')
    op.drop_index('idx_figma_installation_team', table_name='figma_installation')
    op.drop_index('idx_figma_installation_user', table_name='figma_installation')
    op.drop_table('figma_installation')
