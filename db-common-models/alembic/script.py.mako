"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    """
    Apply database schema changes.
    
    This function contains the forward migration logic that will be
    executed when running 'alembic upgrade'. All schema modifications
    should be implemented here using Alembic's op module.
    """
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """
    Revert database schema changes.
    
    This function contains the rollback logic that will be executed
    when running 'alembic downgrade'. It should reverse all changes
    made in the upgrade() function to ensure migrations are reversible.
    """
    ${downgrades if downgrades else "pass"}
