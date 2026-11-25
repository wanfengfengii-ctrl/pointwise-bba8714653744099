from uuid import uuid4

from issue.contributions import count_local_contributions
from issue.envelope import PackageEnvelope
from issue.issue_store import IssuedPackage, IssueStore
from survey.revision_store import RevisionStore
from survey.terminals import validate_name


def freeze_package(
    revisions: RevisionStore, issues: IssueStore, station: str, revision_id: str
) -> IssuedPackage:
    validate_name(station, 'station')
    revision = revisions.get_revision(validate_name(revision_id, 'revision number'))
    if revision.station != station:
        raise ValueError('revision belongs to a different station')
    envelope = PackageEnvelope(
        f'pkg-{uuid4().hex}', revision.batch, revision.station, revision.revision_id,
        revision.terminals, count_local_contributions(revision),
    )
    return issues.save_package(envelope)


def get_package(issues: IssueStore, freeze_id: str) -> IssuedPackage:
    item = issues.find_package(validate_name(freeze_id, 'freeze number'))
    if item is None:
        raise LookupError(f'unknown frozen package: {freeze_id}')
    return item
