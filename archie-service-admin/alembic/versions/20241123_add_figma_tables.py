"""Add Figma integration tables

Revision ID: 20241123_add_figma_tables
Revises:
Create Date: 2024-11-23

This migration creates three tables to support Figma integration functionality:

1. figma_installation: Stores Figma installation metadata and references to Personal Access
   Tokens (PATs) stored in Google Secret Manager. PATs are never stored in the database,
   only their status (active/expired) is tracked.

2. figma_installation_access: Manages role-based sharing of Figma installations, allowing
   ADMIN and SUPER_ADMIN users to grant access to other users. Follows the pattern
   established by github_installation_access table.

3. figma_attachment: Stores lightweight Figma frame URL attachments to projects and
   technical specifications. Only URLs and descriptions are stored - no file downloads
   or uploads are performed.

All tables support soft deletion via deleted_at timestamp columns and include appropriate
indexes for query performance optimization.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20241123_add_figma_tables'
down_revision = None  # Set to the previous migration revision ID
branch_labels = None
depends_on = None


def upgrade():
    """
    Create Figma integration tables with proper constraints and indexes.

    Tables are created in dependency order:
    1. figma_installation (base table, no dependencies)
    2. figma_installation_access (depends on figma_installation)
    3. figma_attachment (depends on figma_installation)

    Each table includes:
    - Primary key (id) as BigInteger
    - Foreign key constraints to maintain referential integrity
    - Unique constraints to prevent duplicate records
    - Indexes on frequently queried columns
    - Soft delete support via deleted_at column
    - Audit timestamps (created_at, updated_at)
    """

    # Table 1: figma_installation
    # Stores Figma installation metadata; PATs are stored in Google Secret Manager
    # with naming pattern: figma-secret-<installation_id>
    op.create_table(
        'figma_installation',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('team_id', sa.BigInteger(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_figma_installation_user_id'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], name='fk_figma_installation_team_id'),
        sa.PrimaryKeyConstraint('id', name='pk_figma_installation')
    )

    # Create indexes for figma_installation
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
        unique=False
    )

    # Table 2: figma_installation_access
    # Manages role-based access control for Figma installations
    # Mirrors the pattern of github_installation_access table
    op.create_table(
        'figma_installation_access',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('figma_installation_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('access_level', sa.String(length=50), nullable=False, server_default='viewer'),
        sa.Column('granted_by', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['figma_installation_id'],
            ['figma_installation.id'],
            name='fk_figma_installation_access_installation_id'
        ),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.id'],
            name='fk_figma_installation_access_user_id'
        ),
        sa.ForeignKeyConstraint(
            ['granted_by'],
            ['users.id'],
            name='fk_figma_installation_access_granted_by'
        ),
        sa.PrimaryKeyConstraint('id', name='pk_figma_installation_access'),
        # Unique constraint prevents duplicate active access grants
        # Allows soft delete history by including deleted_at in constraint
        sa.UniqueConstraint(
            'figma_installation_id',
            'user_id',
            'deleted_at',
            name='uq_figma_installation_access_installation_user_deleted'
        )
    )

    # Create indexes for figma_installation_access
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
        unique=False
    )

    # Table 3: figma_attachment
    # Stores lightweight references to Figma frames attached to projects
    # Only stores URLs and metadata - no file downloads or GCS uploads
    op.create_table(
        'figma_attachment',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('project_id', sa.BigInteger(), nullable=False),
        sa.Column('tech_spec_id', sa.BigInteger(), nullable=True),
        sa.Column('figma_installation_id', sa.BigInteger(), nullable=False),
        sa.Column('frame_url', sa.Text(), nullable=False),
        sa.Column('frame_title', sa.String(length=500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['project_id'],
            ['projects.id'],
            name='fk_figma_attachment_project_id'
        ),
        sa.ForeignKeyConstraint(
            ['tech_spec_id'],
            ['tech_specs.id'],
            name='fk_figma_attachment_tech_spec_id'
        ),
        sa.ForeignKeyConstraint(
            ['figma_installation_id'],
            ['figma_installation.id'],
            name='fk_figma_attachment_installation_id'
        ),
        sa.ForeignKeyConstraint(
            ['created_by'],
            ['users.id'],
            name='fk_figma_attachment_created_by'
        ),
        sa.PrimaryKeyConstraint('id', name='pk_figma_attachment'),
        # Unique constraint ensures same frame URL exists only once per project
        # Last write wins on updates (additive, idempotent behavior)
        sa.UniqueConstraint(
            'project_id',
            'frame_url',
            'deleted_at',
            name='uq_figma_attachment_project_url_deleted'
        )
    )

    # Create indexes for figma_attachment
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
        unique=False
    )


def downgrade():
    """
    Remove Figma integration tables and indexes.

    Drops all created objects in reverse dependency order to maintain
    referential integrity during rollback:
    1. figma_attachment (depends on figma_installation)
    2. figma_installation_access (depends on figma_installation)
    3. figma_installation (base table)

    Indexes are dropped automatically when tables are dropped.
    """

    # Drop figma_attachment table and its indexes
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
    op.drop_index('idx_figma_installation_deleted', table_name='figma_installation')
    op.drop_index('idx_figma_installation_team', table_name='figma_installation')
    op.drop_index('idx_figma_installation_user', table_name='figma_installation')
    op.drop_table('figma_installation')
