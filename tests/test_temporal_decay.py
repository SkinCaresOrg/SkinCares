"""
Tests for temporal decay in compute_user_vector_with_decay.

Key properties verified:
- Recent interactions outweigh older ones
- All-same-age interactions match compute_user_vector output
- Fallback to compute_user_vector when no timestamps present
- lambda_decay=0 (no decay) matches simple mean behaviour
- Irritation signal is stronger than dislike (Rocchio -2.0 vs -1.0)
"""

from datetime import datetime, timedelta, timezone

import numpy as np

from skincarelib.ml_system.feedback_update import (
    UserState,
    compute_user_vector,
    compute_user_vector_with_decay,
)

DIM = 8


def _now():
    return datetime.now(timezone.utc)


def _days_ago(n: int) -> datetime:
    return _now() - timedelta(days=n)


def test_recent_like_outweighs_old_like():
    """A like from yesterday should pull the vector more than one from 90 days ago."""
    vec_old = np.zeros(DIM, dtype=np.float32)
    vec_old[0] = 1.0  # old like points to dim 0

    vec_recent = np.zeros(DIM, dtype=np.float32)
    vec_recent[1] = 1.0  # recent like points to dim 1

    user = UserState(dim=DIM)
    user.add_liked(vec_old, [], timestamp=_days_ago(90))
    user.add_liked(vec_recent, [], timestamp=_days_ago(1))

    result = compute_user_vector_with_decay(user, lambda_decay=0.01)

    # dim 1 (recent) should contribute more than dim 0 (old)
    assert result[1] > result[0]


def test_equal_timestamps_matches_uniform_average():
    """When all interactions happened at the same time, decay weights are equal
    and the result should match compute_user_vector."""
    vec_a = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    vec_b = np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)

    ts = _days_ago(10)
    user_decay = UserState(dim=DIM)
    user_decay.add_liked(vec_a, [], timestamp=ts)
    user_decay.add_liked(vec_b, [], timestamp=ts)

    user_plain = UserState(dim=DIM)
    user_plain.add_liked(vec_a, [])
    user_plain.add_liked(vec_b, [])

    result_decay = compute_user_vector_with_decay(user_decay, lambda_decay=0.01)
    result_plain = compute_user_vector(user_plain)

    np.testing.assert_allclose(result_decay, result_plain, atol=1e-4)


def test_fallback_when_no_timestamps():
    """UserState with no timestamps falls back to compute_user_vector."""
    vec = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)

    user = UserState(dim=DIM)
    # Manually append without timestamp to simulate legacy state
    user.liked_vectors.append(vec)
    user.liked_count += 1
    user.interactions += 1
    # liked_timestamps stays empty

    result_decay = compute_user_vector_with_decay(user, lambda_decay=0.01)
    result_plain = compute_user_vector(user)

    np.testing.assert_allclose(result_decay, result_plain, atol=1e-6)


def test_zero_lambda_matches_plain_vector():
    """lambda_decay=0 means no decay — all weights = 1.0 — should match compute_user_vector."""
    vec_a = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    vec_b = np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)

    user_decay = UserState(dim=DIM)
    user_decay.add_liked(vec_a, [], timestamp=_days_ago(1))
    user_decay.add_liked(vec_b, [], timestamp=_days_ago(90))

    user_plain = UserState(dim=DIM)
    user_plain.add_liked(vec_a, [])
    user_plain.add_liked(vec_b, [])

    result_decay = compute_user_vector_with_decay(user_decay, lambda_decay=0.0)
    result_plain = compute_user_vector(user_plain)

    np.testing.assert_allclose(result_decay, result_plain, atol=1e-4)


def test_irritation_suppresses_more_than_dislike():
    """Irritation (Rocchio -2.0) should suppress output more than dislike (-1.0)."""
    vec_liked = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    vec_neg = np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    ts = _days_ago(5)

    user_dislike = UserState(dim=DIM)
    user_dislike.add_liked(vec_liked, [], timestamp=ts)
    user_dislike.add_disliked(vec_neg, [], timestamp=ts)

    user_irritation = UserState(dim=DIM)
    user_irritation.add_liked(vec_liked, [], timestamp=ts)
    user_irritation.add_irritation(vec_neg, [], timestamp=ts)

    result_dislike = compute_user_vector_with_decay(user_dislike)
    result_irritation = compute_user_vector_with_decay(user_irritation)

    # irritation should suppress dim 1 more → result_irritation[1] < result_dislike[1]
    assert result_irritation[1] < result_dislike[1]


def test_output_is_normalized():
    """Result should always be a unit vector."""
    user = UserState(dim=DIM)
    user.add_liked(np.ones(DIM, dtype=np.float32), [], timestamp=_days_ago(10))
    user.add_disliked(np.ones(DIM, dtype=np.float32) * 0.5, [], timestamp=_days_ago(5))

    result = compute_user_vector_with_decay(user)
    assert abs(np.linalg.norm(result) - 1.0) < 1e-5


def test_misaligned_vectors_and_timestamps_falls_back():
    """If vectors and timestamps are out of sync, fall back to compute_user_vector."""
    vec = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)

    user = UserState(dim=DIM)
    # Manually create misalignment: 2 vectors but only 1 timestamp
    user.liked_vectors.append(vec)
    user.liked_vectors.append(vec)
    user.liked_timestamps.append(_days_ago(5))  # one short
    user.liked_count = 2
    user.interactions = 2

    # Should not crash, and should match plain compute_user_vector
    result_decay = compute_user_vector_with_decay(user, lambda_decay=0.01)
    result_plain = compute_user_vector(user)
    np.testing.assert_allclose(result_decay, result_plain, atol=1e-6)


def test_high_lambda_decays_old_interactions_aggressively():
    """With high lambda, a 60-day-old like should have near-zero influence."""
    vec_old = np.zeros(DIM, dtype=np.float32)
    vec_old[0] = 1.0

    vec_recent = np.zeros(DIM, dtype=np.float32)
    vec_recent[1] = 1.0

    user = UserState(dim=DIM)
    user.add_liked(vec_old, [], timestamp=_days_ago(60))
    user.add_liked(vec_recent, [], timestamp=_days_ago(1))

    result = compute_user_vector_with_decay(user, lambda_decay=0.1)  # half-life ~7 days

    # With lambda=0.1, 60-day weight ≈ e^-6 ≈ 0.0025 vs 1-day weight ≈ e^-0.1 ≈ 0.90
    # dim 1 (recent) should dominate heavily
    assert result[1] > result[0] * 10
