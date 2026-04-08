"""Tests for the auto-classifier module."""

from buoyancy.classifier import classify
from buoyancy.task import Complexity


# ---------------------------------------------------------------------------
# Task type detection — one representative keyword per type
# ---------------------------------------------------------------------------


def test_classify_bugfix():
    task_type, _ = classify("fix the login button crash on mobile")
    assert task_type == "bugfix"


def test_classify_bugfix_hotfix():
    task_type, _ = classify("hotfix for production error in payment service")
    assert task_type == "bugfix"


def test_classify_feature():
    task_type, _ = classify("implement a new user onboarding flow")
    assert task_type == "feature"


def test_classify_feature_add():
    task_type, _ = classify("add dark mode support")
    assert task_type == "feature"


def test_classify_refactor():
    task_type, _ = classify("refactor the authentication module")
    assert task_type == "refactor"


def test_classify_docs():
    task_type, _ = classify("update the README with new API examples")
    assert task_type == "docs"


def test_classify_docs_typo():
    task_type, _ = classify("fix a typo in the contributing guide")
    assert task_type == "bugfix"  # "fix" hits bugfix first


def test_classify_research():
    task_type, _ = classify("research available open-source graph databases")
    assert task_type == "research"


def test_classify_code_review():
    task_type, _ = classify("review the PR for the payment integration")
    assert task_type == "code-review"


def test_classify_test():
    task_type, _ = classify("add unit tests for the parser module")
    assert task_type == "test"  # "test" now has higher priority than "add"


def test_classify_test_coverage():
    task_type, _ = classify("increase coverage for the billing module")
    assert task_type == "test"


def test_classify_deploy():
    task_type, _ = classify("deploy the new release to production")
    assert task_type == "deploy"


def test_classify_config():
    task_type, _ = classify("setup the CI pipeline for the monorepo")
    assert task_type == "config"


# ---------------------------------------------------------------------------
# Complexity estimation
# ---------------------------------------------------------------------------


def test_complexity_simple_keyword():
    _, complexity = classify("quick fix for the navbar alignment")
    assert complexity == Complexity.SIMPLE


def test_complexity_trivial_very_short():
    _, complexity = classify("fix bug")
    assert complexity == Complexity.TRIVIAL


def test_complexity_complex_keyword():
    _, complexity = classify("complex refactor of the entire billing pipeline")
    assert complexity == Complexity.COMPLEX


def test_complexity_epic_many_files():
    description = (
        "migrate auth.py, models.py, views.py, serializers.py, urls.py "
        "and tests.py to the new framework"
    )
    _, complexity = classify(description)
    assert complexity in (Complexity.COMPLEX, Complexity.EPIC)


def test_complexity_moderate_medium_description():
    _, complexity = classify(
        "implement a basic rate limiter for the public API endpoints with retry logic and backoff strategy"
    )
    assert complexity == Complexity.MODERATE


def test_complexity_simple_short_description():
    _, complexity = classify("update the footer copyright year in the layout component")
    assert complexity == Complexity.SIMPLE


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_classify_empty_string():
    task_type, complexity = classify("")
    assert task_type == "feature"
    assert complexity == Complexity.MODERATE


def test_classify_whitespace_only():
    task_type, complexity = classify("   ")
    assert task_type == "feature"
    assert complexity == Complexity.MODERATE


def test_classify_unknown_task_defaults_to_feature():
    task_type, _ = classify("do the thing with the stuff")
    assert task_type == "feature"


def test_classify_returns_tuple():
    result = classify("fix the broken search index")
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_classify_complexity_is_complexity_enum():
    _, complexity = classify("investigate the memory leak in the worker process")
    assert isinstance(complexity, Complexity)
