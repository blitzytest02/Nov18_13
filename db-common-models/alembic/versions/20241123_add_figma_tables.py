"""Add Figma integration tables

Revision ID: 20241123_add_figma_tables
Revises:
Create Date: 2024-11-23

This migration creates three tables for comprehensive Figma integration support:
1. figma_installation - Stores Figma integration metadata and ownership
2. figma_installation_access - Manages role-based sharing of integrations
3. figma_attachment - Stores Figma frame URL attachments to projects

All tables include soft delete support via deleted_at timestamps and proper
indexing for query performance.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20241123_add_figma_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """
    Create Figma integration tables with proper foreign keys, indexes, and constraints.

    Tables are created in dependency order to satisfy foreign key constraints.
    """
    # Create figma_installation table
    # Stores core integration metadata including owner, team association, and PAT status
    op.create_table(
        'figma_installation',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('user_id', sa.BigInteger(), nullable=False,
                  comment='Owner of the Figma installation'),
        sa.Column('team_id', sa.BigInteger(), nullable=True,
                  comment='Optional team association for shared installations'),
        sa.Column('name', sa.String(length=255), nullable=False,
                  comment='Display name for the installation'),
        sa.Column('description', sa.Text(), nullable=True,
                  comment='Optional description of the installation purpose'),
        sa.Column('status', sa.String(length=50), nullable=False,
                  server_default='active',
                  comment='Installation status: active, expired, disabled - tracks PAT validity'),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('NOW()'),
                  comment='Timestamp of installation creation'),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('NOW()'),
                  comment='Timestamp of last update'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True,
                  comment='Soft delete timestamp - null means active'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_figma_installation_user'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], name='fk_figma_installation_team'),
        sa.PrimaryKeyConstraint('id', name='pk_figma_installation')
    )

    # Create indexes for figma_installation to optimize common queries
    op.create_index(
        'idx_figma_installation_user',
        'figma_installation',
        ['user_id'],
        unique=False
    )
    op.create_index(
        'idx_figma_installation_team',
        'figma_installation',
        ['team_id'],
        unique=False
    )
    op.create_index(
        'idx_figma_installation_deleted',
        'figma_installation',
        ['deleted_at'],
        unique=False,
        postgresql_where=sa.text('deleted_at IS NOT NULL')
    )

    # Create figma_installation_access table
    # Manages role-based access control for sharing installations across users
    # Mirrors github_installation_access pattern per Agent Action Plan requirement A.2.4
    op.create_table(
        'figma_installation_access',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('figma_installation_id', sa.BigInteger(), nullable=False,
                  comment='Reference to the shared Figma installation'),
        sa.Column('user_id', sa.BigInteger(), nullable=False,
                  comment='User who has been granted access'),
        sa.Column('access_level', sa.String(length=50), nullable=False,
                  server_default='viewer',
                  comment='Access level: viewer, editor, admin'),
        sa.Column('granted_by', sa.BigInteger(), nullable=False,
                  comment='Admin user who granted this access'),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('NOW()'),
                  comment='Timestamp when access was granted'),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('NOW()'),
                  comment='Timestamp of last access update'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True,
                  comment='Soft delete timestamp for revoked access'),
        sa.ForeignKeyConstraint(
            ['figma_installation_id'],
            ['figma_installation.id'],
            name='fk_figma_access_installation'
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_figma_access_user'),
        sa.ForeignKeyConstraint(['granted_by'], ['users.id'], name='fk_figma_access_granted_by'),
        sa.PrimaryKeyConstraint('id', name='pk_figma_installation_access'),
        # Unique constraint prevents duplicate active access grants
        # Allows soft delete history by including deleted_at in constraint
        sa.UniqueConstraint(
            'figma_installation_id',
            'user_id',
            'deleted_at',
            name='uq_figma_access_installation_user_deleted'
        )
    )

    # Create indexes for figma_installation_access to optimize access queries
    op.create_index(
        'idx_figma_access_installation',
        'figma_installation_access',
        ['figma_installation_id'],
        unique=False
    )
    op.create_index(
        'idx_figma_access_user',
        'figma_installation_access',
        ['user_id'],
        unique=False
    )
    op.create_index(
        'idx_figma_access_deleted',
        'figma_installation_access',
        ['deleted_at'],
        unique=False,
        postgresql_where=sa.text('deleted_at IS NOT NULL')
    )

    # Create figma_attachment table
    # Stores lightweight Figma frame URL attachments to projects
    # Per requirement A.7.2: URL + description only, no file downloads
    op.create_table(
        'figma_attachment',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('project_id', sa.BigInteger(), nullable=False,
                  comment='Required project association'),
        sa.Column('tech_spec_id', sa.BigInteger(), nullable=True,
                  comment='Optional technical specification association'),
        sa.Column('figma_installation_id', sa.BigInteger(), nullable=False,
                  comment='Figma installation used for access validation'),
        sa.Column('frame_url', sa.Text(), nullable=False,
                  comment='Full Figma frame URL (e.g., https://www.figma.com/file/...)'),
        sa.Column('frame_title', sa.String(length=500), nullable=True,
                  comment='Frame title retrieved from Figma API during validation'),
        sa.Column('description', sa.Text(), nullable=True,
                  comment='User-provided description of the frame attachment'),
        sa.Column('created_by', sa.BigInteger(), nullable=False,
                  comment='User who created the attachment'),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('NOW()'),
                  comment='Timestamp of attachment creation'),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('NOW()'),
                  comment='Timestamp of last update'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True,
                  comment='Soft delete timestamp'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name='fk_figma_attachment_project'),
        sa.ForeignKeyConstraint(['tech_spec_id'], ['tech_specs.id'], name='fk_figma_attachment_techspec'),
        sa.ForeignKeyConstraint(
            ['figma_installation_id'],
            ['figma_installation.id'],
            name='fk_figma_attachment_installation'
        ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_figma_attachment_created_by'),
        sa.PrimaryKeyConstraint('id', name='pk_figma_attachment'),
        # Unique constraint ensures same frame URL only exists once per project
        # Last write wins on updates (additive, idempotent behavior per requirement A.7.1.2)
        sa.UniqueConstraint(
            'project_id',
            'frame_url',
            'deleted_at',
            name='uq_figma_attachment_project_url_deleted'
        )
    )

    # Create indexes for figma_attachment to optimize filtering and lookups
    op.create_index(
        'idx_figma_attachment_project',
        'figma_attachment',
        ['project_id'],
        unique=False
    )
    op.create_index(
        'idx_figma_attachment_techspec',
        'figma_attachment',
        ['tech_spec_id'],
        unique=False
    )
    op.create_index(
        'idx_figma_attachment_installation',
        'figma_attachment',
        ['figma_installation_id'],
        unique=False
    )
    op.create_index(
        'idx_figma_attachment_deleted',
        'figma_attachment',
        ['deleted_at'],
        unique=False,
        postgresql_where=sa.text('deleted_at IS NOT NULL')
    )


def downgrade():
    """
    Drop all Figma integration tables and indexes in reverse dependency order.

    This ensures proper foreign key constraint handling during rollback.
    """
    # Drop figma_attachment table and its indexes first (has foreign keys to figma_installation)
    op.drop_index('idx_figma_attachment_deleted', table_name='figma_attachment')
    op.drop_index('idx_figma_attachment_installation', table_name='figma_attachment')
    op.drop_index('idx_figma_attachment_techspec', table_name='figma_attachment')
    op.drop_index('idx_figma_attachment_project', table_name='figma_attachment')
    op.drop_table('figma_attachment')

    # Drop figma_installation_access table and its indexes (has foreign key to figma_installation)
    op.drop_index('idx_figma_access_deleted', table_name='figma_installation_access')
    op.drop_index('idx_figma_access_user', table_name='figma_installation_access')
    op.drop_index('idx_figma_access_installation', table_name='figma_installation_access')
    op.drop_table('figma_installation_access')

    # Drop figma_installation table and its indexes last (parent table)
    op.drop_index('idx_figma_installation_deleted', table_name='figma_installation')
    op.drop_index('idx_figma_installation_team', table_name='figma_installation')
    op.drop_index('idx_figma_installation_user', table_name='figma_installation')
    op.drop_table('figma_installation')
