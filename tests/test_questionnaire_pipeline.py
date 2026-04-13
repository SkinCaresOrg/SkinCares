from fastapi.testclient import TestClient
import pytest
from datetime import datetime, timedelta, timezone

import importlib
from deployment.api.app import app, PRODUCTS


client = TestClient(app)
app_module = importlib.import_module("deployment.api.app")


def _onboard_user() -> str:
    response = client.post(
        "/api/onboarding",
        json={
            "skin_type": "sensitive",
            "concerns": ["redness", "dryness"],
            "sensitivity_level": "very_sensitive",
            "ingredient_exclusions": [],
            "price_range": "mid_range",
            "routine_size": "basic",
            "product_interests": ["moisturizer", "cleanser"],
        },
    )
    assert response.status_code == 200
    return response.json()["user_id"]


def _is_fragrance_product(product_id: int) -> bool:
    product = PRODUCTS.get(product_id)
    if product is None:
        return False
    return any("fragrance" in ingredient.lower() for ingredient in product.ingredients)


def _first_fragrance_product_id() -> int:
    for product_id, product in PRODUCTS.items():
        if any("fragrance" in ingredient.lower() for ingredient in product.ingredients):
            return product_id
    pytest.skip("No fragrance-containing product found for decay test")


def _first_product_with_ingredients():
    for _, product in PRODUCTS.items():
        if product.ingredients:
            return product
    pytest.skip("No product with ingredients found")


def test_questionnaire_feedback_has_more_learning_signal_than_raw_swipe() -> None:
    user_id = _onboard_user()

    before = client.get(f"/api/debug/user-state/{user_id}")
    assert before.status_code == 200
    before_state = before.json()

    not_tried = client.post(
        "/api/feedback",
        json={"user_id": user_id, "product_id": 1, "has_tried": False},
    )
    assert not_tried.status_code == 200

    after_raw = client.get(f"/api/debug/user-state/{user_id}")
    assert after_raw.status_code == 200
    after_raw_state = after_raw.json()

    assert after_raw_state["interactions"] == before_state["interactions"]
    assert after_raw_state["reason_signal_count"] == before_state["reason_signal_count"]

    tried = client.post(
        "/api/feedback",
        json={
            "user_id": user_id,
            "product_id": 2,
            "has_tried": True,
            "reaction": "dislike",
            "reason_tags": ["contains_fragrance"],
            "free_text": "contains fragrance",
        },
    )
    assert tried.status_code == 200

    after_questionnaire = client.get(f"/api/debug/user-state/{user_id}")
    assert after_questionnaire.status_code == 200
    after_questionnaire_state = after_questionnaire.json()

    assert (
        after_questionnaire_state["interactions"] >= after_raw_state["interactions"] + 1
    )
    assert (
        after_questionnaire_state["reason_signal_count"]
        >= after_raw_state["reason_signal_count"] + 1
    )
    assert after_questionnaire_state["avoid_ingredient_count"] >= 1


def test_contains_fragrance_feedback_reduces_fragrance_in_top_recommendations() -> None:
    fragrance_ids = [
        product_id
        for product_id, product in PRODUCTS.items()
        if any("fragrance" in ingredient.lower() for ingredient in product.ingredients)
    ]
    if len(fragrance_ids) < 5:
        pytest.skip("Not enough fragrance products to run this pipeline test")

    user_id = _onboard_user()

    recs_before = client.get(f"/api/recommendations/{user_id}", params={"limit": 10})
    assert recs_before.status_code == 200

    for product_id in fragrance_ids[:5]:
        response = client.post(
            "/api/feedback",
            json={
                "user_id": user_id,
                "product_id": product_id,
                "has_tried": True,
                "reaction": "dislike",
                "reason_tags": ["contains_fragrance"],
                "free_text": "contains fragrance",
            },
        )
        assert response.status_code == 200

    # After feedback, verify that fragrance products are heavily penalized
    # (Note: fragrance products naturally rank low, so top 10 may not change)
    # But we can verify they get penalized by checking the scores directly via the debug endpoint
    fragrance_product_tests = fragrance_ids[:3]  # Test first 3 fragrance products
    
    for frag_id in fragrance_product_tests:
        debug_response = client.get(f"/api/debug/product-score/{user_id}/{frag_id}")
        assert debug_response.status_code == 200
        
        score_data = debug_response.json()
        # After disliking fragrance products, they should score very low
        # (near zero due to structured adjustment penalty)
        assert score_data["score"] < 0.001, (
            f"Fragrance product {frag_id} should score near-zero after dislike feedback, "
            f"but got {score_data['score']}"
        )
    
    # Also verify that non-fragrance products in top 10 still score well
    # and that no fragrance products appear in top 10 recommendations
    recs_after = client.get(f"/api/recommendations/{user_id}", params={"limit": 10})
    assert recs_after.status_code == 200
    after_products = recs_after.json()["products"]
    after_fragrance_count = sum(
        1 for product in after_products if _is_fragrance_product(product["product_id"])
    )
    
    # Verify no fragrance in top recommendations after dislike
    assert after_fragrance_count == 0, (
        f"Expected no fragrance products in top recommendations after dislike feedback, "
        f"but found {after_fragrance_count}"
    )



def test_startup_replay_reads_questionnaire_table_and_updates_model_state() -> None:
    user_id = _onboard_user()

    response = client.post(
        "/api/feedback",
        json={
            "user_id": user_id,
            "product_id": 3,
            "has_tried": True,
            "reaction": "like",
            "reason_tags": ["hydrating"],
            "free_text": "hydrates well",
        },
    )
    assert response.status_code == 200

    # Simulate cold start without persisted processed IDs, then replay from DB rows.
    app_module.USER_STATES = {}
    app_module.PROCESSED_QUESTIONNAIRE_RESPONSE_IDS = set()
    app_module.QUESTIONNAIRE_PIPELINE_STATUS = {
        "startup_replay_processed": 0,
        "startup_replay_skipped": 0,
        "startup_replay_errors": 0,
    }

    app_module._replay_questionnaire_feedback_from_db()

    replayed_state = client.get(f"/api/debug/user-state/{user_id}")
    assert replayed_state.status_code == 200
    replayed_payload = replayed_state.json()

    assert replayed_payload["interactions"] >= 1
    assert replayed_payload["reason_signal_count"] >= 1

    status = client.get("/api/debug/questionnaire-pipeline-status")
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["processed_response_ids_count"] >= 1


def test_manual_replay_endpoint_returns_timestamp_and_processed_ids() -> None:
    user_id = _onboard_user()
    feedback = client.post(
        "/api/feedback",
        json={
            "user_id": user_id,
            "product_id": 4,
            "has_tried": True,
            "reaction": "dislike",
            "reason_tags": ["contains_fragrance"],
            "free_text": "contains fragrance",
        },
    )
    assert feedback.status_code == 200

    # Force replay to process from DB again for this test run.
    app_module.PROCESSED_QUESTIONNAIRE_RESPONSE_IDS = set()
    app_module.QUESTIONNAIRE_PIPELINE_STATUS = {
        "startup_replay_processed": 0,
        "startup_replay_skipped": 0,
        "startup_replay_errors": 0,
        "last_run_processed_ids": [],
        "last_run_timestamp": None,
        "last_run_source": None,
    }

    replay = client.post("/api/debug/questionnaire-pipeline-replay")
    assert replay.status_code == 200
    replay_payload = replay.json()

    assert replay_payload["last_run_source"] == "manual"
    assert replay_payload["last_run_timestamp"]
    assert isinstance(replay_payload["last_run_processed_ids"], list)
    assert replay_payload["processed_response_ids_count"] >= 1


def test_questionnaire_completion_metrics_reflect_new_feedback() -> None:
    before = client.get("/api/debug/questionnaire-completion-metrics")
    assert before.status_code == 200
    before_metrics = before.json()["all_time"]

    user_id = _onboard_user()

    responses = [
        {"user_id": user_id, "product_id": 11, "has_tried": False},
        {
            "user_id": user_id,
            "product_id": 12,
            "has_tried": True,
            "reaction": "like",
            "reason_tags": ["good_value"],
            "free_text": "good value",
        },
        {
            "user_id": user_id,
            "product_id": 13,
            "has_tried": True,
            "reaction": "dislike",
            "reason_tags": ["price_too_high"],
            "free_text": "too expensive",
        },
    ]

    for payload in responses:
        response = client.post("/api/feedback", json=payload)
        assert response.status_code == 200

    after = client.get("/api/debug/questionnaire-completion-metrics")
    assert after.status_code == 200
    after_metrics = after.json()["all_time"]

    assert after_metrics["total_swipes"] >= before_metrics["total_swipes"] + 3
    assert after_metrics["completed_questionnaires"] >= (
        before_metrics["completed_questionnaires"] + 2
    )
    assert after_metrics["skipped_questionnaires"] >= (
        before_metrics["skipped_questionnaires"] + 1
    )
    assert 0.0 <= float(after_metrics["completion_rate"]) <= 1.0


def test_questionnaire_outcome_metrics_track_cohorts_and_uplift() -> None:
    before = client.get("/api/debug/questionnaire-outcome-metrics")
    assert before.status_code == 200
    before_payload = before.json()

    before_after_skipped_samples = int(
        before_payload["cohorts"]["after_skipped"]["samples"]
    )
    before_after_completed_samples = int(
        before_payload["cohorts"]["after_completed"]["samples"]
    )

    user_a = _onboard_user()
    user_b = _onboard_user()

    sequence = [
        # Contributes one after_skipped sample via next completed=like
        {"user_id": user_a, "product_id": 21, "has_tried": False},
        {
            "user_id": user_a,
            "product_id": 22,
            "has_tried": True,
            "reaction": "like",
            "reason_tags": ["hydrating"],
            "free_text": "liked it",
        },
        # Contributes one after_completed sample via next completed=dislike
        {
            "user_id": user_b,
            "product_id": 23,
            "has_tried": True,
            "reaction": "like",
            "reason_tags": ["good_value"],
            "free_text": "good value",
        },
        {
            "user_id": user_b,
            "product_id": 24,
            "has_tried": True,
            "reaction": "dislike",
            "reason_tags": ["too_heavy"],
            "free_text": "too heavy",
        },
    ]

    for payload in sequence:
        response = client.post("/api/feedback", json=payload)
        assert response.status_code == 200

    after = client.get("/api/debug/questionnaire-outcome-metrics")
    assert after.status_code == 200
    after_payload = after.json()

    assert (
        int(after_payload["cohorts"]["after_skipped"]["samples"])
        >= before_after_skipped_samples + 1
    )
    assert (
        int(after_payload["cohorts"]["after_completed"]["samples"])
        >= before_after_completed_samples + 1
    )

    overall = after_payload["overall"]
    assert overall["total_swipes"] >= 1
    assert overall["completed_questionnaires"] >= 1
    assert overall["skipped_questionnaires"] >= 1

    uplift = after_payload["uplift"]
    assert "absolute_like_rate_uplift" in uplift
    assert "relative_like_rate_uplift" in uplift


def test_reason_signal_time_decay_reduces_old_reason_impact() -> None:
    product_id = _first_fragrance_product_id()
    product = PRODUCTS[product_id]
    user_id = _onboard_user()
    user_state = app_module.get_user_state(user_id)

    now = datetime.now(timezone.utc)
    user_state.reason_tag_preferences = {"contains_fragrance": -1.0}
    user_state.reason_tag_last_seen_at = {
        "contains_fragrance": now.isoformat(),
    }

    recent_adjustment = app_module._compute_reason_adjustment(product, user_state)

    user_state.reason_tag_last_seen_at = {
        "contains_fragrance": (now - timedelta(days=365)).isoformat(),
    }
    stale_adjustment = app_module._compute_reason_adjustment(product, user_state)

    assert recent_adjustment < stale_adjustment
    assert abs(recent_adjustment) > abs(stale_adjustment)


def test_structured_signal_time_decay_reduces_old_avoid_impact() -> None:
    product_id = _first_fragrance_product_id()
    product = PRODUCTS[product_id]
    matched_ingredient = next(
        (
            app_module._normalize_ingredient_name(ingredient)
            for ingredient in product.ingredients
            if app_module._normalize_ingredient_name(ingredient)
        ),
        None,
    )
    if matched_ingredient is None:
        pytest.skip("No usable ingredient token for structured decay test")

    user_id = _onboard_user()
    user_state = app_module.get_user_state(user_id)
    user_profile = app_module.USER_PROFILES[user_id]

    now = datetime.now(timezone.utc)
    user_state.avoid_ingredients = {matched_ingredient: 1.0}
    user_state.avoid_ingredient_last_seen_at = {matched_ingredient: now.isoformat()}

    recent_adjustment = app_module._compute_structured_adjustment(
        product,
        user_state,
        user_profile,
    )

    user_state.avoid_ingredient_last_seen_at = {
        matched_ingredient: (now - timedelta(days=365)).isoformat()
    }
    stale_adjustment = app_module._compute_structured_adjustment(
        product,
        user_state,
        user_profile,
    )

    assert recent_adjustment < stale_adjustment
    assert abs(recent_adjustment) > abs(stale_adjustment)


def test_conflict_policy_avoid_overrides_preferred_for_same_ingredient() -> None:
    product = _first_product_with_ingredients()
    ingredient_key = app_module._normalize_ingredient_name(product.ingredients[0])
    if not ingredient_key:
        pytest.skip("No normalized ingredient key available")

    user_id = _onboard_user()
    user_state = app_module.get_user_state(user_id)
    user_profile = app_module.USER_PROFILES[user_id]

    user_state.avoid_ingredients = {ingredient_key: 1.0}
    user_state.preferred_ingredients = {ingredient_key: 5.0}

    with_conflict = app_module._compute_structured_adjustment(
        product,
        user_state,
        user_profile,
    )

    user_state.preferred_ingredients = {}
    avoid_only = app_module._compute_structured_adjustment(
        product,
        user_state,
        user_profile,
    )

    assert with_conflict < 0
    assert with_conflict == pytest.approx(avoid_only, rel=1e-6, abs=1e-6)


def test_conflict_policy_profile_exclusion_overrides_preferred_fragrance() -> None:
    fragrance_product_id = _first_fragrance_product_id()
    user_id = _onboard_user()
    user_state = app_module.get_user_state(user_id)
    user_profile = app_module.USER_PROFILES[user_id]

    user_profile.ingredient_exclusions = ["fragrance"]
    user_state.preferred_ingredients = {"fragrance": 10.0}

    recs = client.get(f"/api/recommendations/{user_id}", params={"limit": 50})
    assert recs.status_code == 200

    returned_ids = [product["product_id"] for product in recs.json()["products"]]
    assert fragrance_product_id not in returned_ids
    assert all(not _is_fragrance_product(product_id) for product_id in returned_ids)


def test_questionnaire_debug_endpoints_blocked_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "DEBUG_ENDPOINTS_ENABLED", False)

    status_response = client.get("/api/debug/questionnaire-pipeline-status")
    completion_response = client.get("/api/debug/questionnaire-completion-metrics")
    outcome_response = client.get("/api/debug/questionnaire-outcome-metrics")
    replay_response = client.post("/api/debug/questionnaire-pipeline-replay")
    user_state_response = client.get("/api/debug/user-state/nonexistent_user")
    product_score_response = client.get("/api/debug/product-score/nonexistent_user/1")

    assert status_response.status_code == 404
    assert completion_response.status_code == 404
    assert outcome_response.status_code == 404
    assert replay_response.status_code == 404
    assert user_state_response.status_code == 404
    assert product_score_response.status_code == 404
    assert user_state_response.json().get("detail") == "Not found"
    assert product_score_response.json().get("detail") == "Not found"
