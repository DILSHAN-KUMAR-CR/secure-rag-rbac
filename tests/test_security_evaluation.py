import pytest

import app.evaluate_security as evaluation
from app.rag_service import PreparedContext
from app.schemas import SourceCitation
from tests.test_permission_aware_retrieval import retrieval_test_app


HANDBOOK_SOURCE = SourceCitation(
    source_number=1,
    document_id=1,
    document_title="Employee Handbook",
    chunk_id=1,
    page_number=1,
)
SALARY_SOURCE = SourceCitation(
    source_number=1,
    document_id=2,
    document_title="Salary Records",
    chunk_id=2,
    page_number=1,
)


def _expected_context(_session, query: str, role: str, _top_k: int):
    if "telecommuting" in query:
        return PreparedContext("Employee Handbook remote days", [HANDBOOK_SOURCE])
    if role == "Employee":
        return PreparedContext("", [])
    return PreparedContext("Fictional annual salary", [SALARY_SOURCE])


def test_evaluation_scores_expected_sources_without_gemini(
    retrieval_test_app, monkeypatch
) -> None:
    _client, session = retrieval_test_app
    monkeypatch.setattr(evaluation, "prepare_authorized_context", _expected_context)

    report = evaluation.evaluate(session, repeats=2)

    assert report["passed"] is True
    assert report["trial_count"] == 10
    assert report["restricted_trial_count"] == 4
    assert report["unauthorized_exposures"] == 0
    assert report["expected_source_match_rate_percent"] == 100.0
    assert report["gemini_calls"] == 0
    assert "720000" not in str(report)


def test_evaluation_detects_leaked_context_without_a_citation(
    retrieval_test_app, monkeypatch
) -> None:
    _client, session = retrieval_test_app

    def leaking_context(session, query, role, top_k):
        if role == "Employee" and "salary" in query:
            return PreparedContext("720000 rupees", [])
        if role == "Employee" and "compensation" in query:
            return PreparedContext("720000 rupees", [])
        return _expected_context(session, query, role, top_k)

    monkeypatch.setattr(evaluation, "prepare_authorized_context", leaking_context)
    report = evaluation.evaluate(session, repeats=1)

    assert report["passed"] is False
    assert report["unauthorized_exposures"] == 2
    assert report["restricted_exposures"] == 2
    assert "720000" not in str(report)


def test_evaluation_rejects_changed_sample_permissions(
    retrieval_test_app
) -> None:
    _client, session = retrieval_test_app
    # The benchmark must not silently treat a different policy as its baseline.
    from app.models import DocumentPermission
    from sqlalchemy import delete

    session.execute(delete(DocumentPermission).where(DocumentPermission.document_id == 2))
    session.commit()
    with pytest.raises(ValueError, match="Sample document roles differ"):
        evaluation.evaluate(session, repeats=1)


def test_extended_profile_covers_all_roles_and_adversarial_queries(
    retrieval_test_app, monkeypatch
) -> None:
    _client, session = retrieval_test_app
    document_ids = {
        title: index
        for index, title in enumerate(evaluation.EXTENDED_PERMISSIONS, start=1)
    }
    permitted_ids = {
        role: {
            document_ids[title]
            for title, roles in evaluation.EXTENDED_PERMISSIONS.items()
            if role in roles
        }
        for role in ("Employee", "HR", "Admin")
    }
    monkeypatch.setattr(
        evaluation,
        "_validate_sample_dataset",
        lambda _session, _profile: permitted_ids,
    )

    cases_by_request = {
        (case.role, case.query): case for case in evaluation.EXTENDED_CASES
    }

    def expected_extended_context(_session, query, role, _top_k):
        case = cases_by_request[(role, query)]
        if case.expected_source is None:
            return PreparedContext("", [])
        citation = SourceCitation(
            source_number=1,
            document_id=document_ids[case.expected_source],
            document_title=case.expected_source,
            chunk_id=document_ids[case.expected_source],
            page_number=1,
        )
        return PreparedContext(f"Permitted {case.expected_source}", [citation])

    monkeypatch.setattr(
        evaluation,
        "prepare_authorized_context",
        expected_extended_context,
    )
    report = evaluation.evaluate_profile(
        session,
        evaluation.EXTENDED_PROFILE,
        repeats=1,
    )

    assert report["passed"] is True
    assert report["profile"] == "extended"
    assert report["case_count"] == len(evaluation.EXTENDED_CASES) == 14
    assert report["unauthorized_exposure_rate_percent"] == 0.0
    assert report["provider_calls_avoided"] == 7
    assert set(report["category_summary"]) == {
        "adversarial_query",
        "authorization",
        "indirect_query",
    }


def test_extended_profile_detects_admin_only_text_leaking_to_hr(
    retrieval_test_app, monkeypatch
) -> None:
    _client, session = retrieval_test_app
    profile = evaluation.DatasetProfile(
        name="hr-leak-test",
        permissions={"System Configuration": {"Admin"}},
        cases=(
            evaluation.EvaluationCase(
                "hr_system_blocked",
                "HR",
                "What is the recovery code?",
                None,
            ),
        ),
        forbidden_canaries={
            "Employee": (),
            "HR": ("production recovery code",),
            "Admin": (),
        },
    )
    monkeypatch.setattr(
        evaluation,
        "_validate_sample_dataset",
        lambda _session, _profile: {"Employee": set(), "HR": set(), "Admin": {1}},
    )
    monkeypatch.setattr(
        evaluation,
        "prepare_authorized_context",
        lambda *_args: PreparedContext("production recovery code", []),
    )

    report = evaluation.evaluate_profile(session, profile, repeats=1)

    assert report["passed"] is False
    assert report["unauthorized_exposures"] == 1
    assert report["restricted_exposures"] == 1
