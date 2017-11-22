"""unify-scm-source-types

Revision ID: a8654abcec65
Revises: fdec9947f8a1
Create Date: 2017-10-13 14:49:22.183416

"""

# revision identifiers, used by Alembic.
revision = 'a8654abcec65'
down_revision = 'fdec9947f8a1'

from alembic import op
import sqlalchemy as sa
import json

from coprs import models, db

def upgrade():
    session = sa.orm.sessionmaker(bind=op.get_bind())()

    for build in session.query(models.Build).filter(models.Build.source_type == 3):
        source_dict = build.source_json_dict
        new_source_dict = {
            'type': 'git',
            'clone_url': source_dict.get('git_url') or '',
            'committish': source_dict.get('git_branch') or '',
            'subdirectory': source_dict.get('git_dir') or '',
            'spec': '',
            'srpm_build_method': 'tito_test' if source_dict.get('tito_test') else 'tito',
        }
        build.source_json = json.dumps(new_source_dict)
        build.source_type = 8
        session.add(build)

    for build in session.query(models.Build).filter(models.Build.source_type == 4):
        source_dict = build.source_json_dict
        new_source_dict = {
            'type': source_dict.get('scm_type') or 'git',
            'clone_url': source_dict.get('scm_url') or '',
            'committish': source_dict.get('scm_branch') or '',
            'subdirectory': source_dict.get('scm_subdir') or '',
            'spec': source_dict.get('spec') or '',
            'srpm_build_method': 'rpkg',
        }
        build.source_json = json.dumps(new_source_dict)
        build.source_type = 8
        session.add(build)

    for build in session.query(models.Build).filter(models.Build.source_type == 7):
        source_dict = build.source_json_dict
        new_source_dict = {
            'type': 'git',
            'clone_url': source_dict.get('clone_url') or '',
            'committish': source_dict.get('branch') or '',
            'subdirectory': '',
            'spec': '',
            'srpm_build_method': 'rpkg',
        }
        build.source_json = json.dumps(new_source_dict)
        build.source_type = 8
        session.add(build)

    session.commit()


def downgrade():
    pass
