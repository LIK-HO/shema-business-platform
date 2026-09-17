from shema_platform.application.identity import IdentityDirectory, IdentityMatch
from shema_platform.domain.identity import Identity, IdentityState, Resolution


def test_identity_directory_deduplicates_across_all_lifecycle_states() -> None:
    directory = IdentityDirectory(
        (
            Identity("pool-1", "ООО Альфа", IdentityState.CANDIDATE, tax_id="7700000000"),
            Identity("client-1", "ООО Бета", IdentityState.ACTIVE, tax_id="7700000001"),
            Identity("verified-1", "ООО Гамма", IdentityState.VERIFIED, tax_id="7700000002"),
        )
    )

    result = directory.resolve(
        Identity("incoming", "Альфа", IdentityState.RAW, tax_id="7700000000")
    )

    assert result.match is IdentityMatch.EXISTING
    assert result.resolution is Resolution.MERGE
    assert result.existing_identity_ids == ("pool-1",)


def test_identity_directory_allows_new_tax_id() -> None:
    directory = IdentityDirectory()
    result = directory.resolve(
        Identity("incoming", "ООО Дельта", IdentityState.RAW, tax_id="7700000003")
    )

    assert result.match is IdentityMatch.NEW
    assert result.resolution is Resolution.KEEP_SEPARATE


def test_identity_directory_quarantines_candidate_without_tax_id() -> None:
    directory = IdentityDirectory()
    result = directory.resolve(
        Identity("incoming", "Без реквизита", IdentityState.RAW)
    )

    assert result.match is IdentityMatch.REVIEW
    assert result.resolution is Resolution.QUARANTINE
