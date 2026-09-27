import json
from pathlib import Path


def test_candidate_provenance_contract_is_fail_closed_on_identity_and_ranking_expansion() -> None:
    path = Path(__file__).parents[1] / "architecture" / "search_candidate_provenance_contract.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["network_execution_enabled"] is False
    assert payload["ranking_authority"] is False
    assert payload["qualification_authority"] is False
    assert payload["persistence_authority"] == "none"
    assert "exact_tax_id_match_is_mergeable_when_no_conflicting_registration_id_exists" in payload[
        "merge_rules"
    ]
    assert "exact_registration_id_match_is_mergeable_when_no_conflicting_tax_id_exists" in payload[
        "merge_rules"
    ]
    assert "name_or_other_fuzzy_similarity_is_not_an_identity_merge_rule" in payload[
        "merge_rules"
    ]
    assert "canonical_identity_mutation" in payload["non_goals"]
    assert "fuzzy_entity_resolution" in payload["non_goals"]


def test_candidate_provenance_contract_preserves_source_evidence_without_global_score() -> None:
    path = Path(__file__).parents[1] / "architecture" / "search_candidate_provenance_contract.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["provenance_rules"] == [
        "primary_source_ref_is_preserved",
        "all_supporting_source_refs_are_retained_in_stable_first-seen_order",
        "contact_refs_are_unioned_deterministically_for_a_confirmed_merge",
        "search_order_remains_the_only_result-order authority",
        "candidate_consolidation_does_not_promote_canonical_identity",
    ]
