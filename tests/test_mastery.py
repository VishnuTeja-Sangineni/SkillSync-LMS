"""Tests for mastery calculation and forgetting decay formulas."""

from datetime import datetime, timezone, timedelta
from app.services.mastery import compute_mastery_update, apply_forgetting_decay


def test_mastery_update_difficulty_weights():
    """Correct answer on hard question raises mastery more than on easy question."""
    initial = 0.5
    boost_hard = compute_mastery_update(initial, is_correct=True, difficulty="hard") - initial
    boost_medium = compute_mastery_update(initial, is_correct=True, difficulty="medium") - initial
    boost_easy = compute_mastery_update(initial, is_correct=True, difficulty="easy") - initial

    assert boost_hard > boost_medium > boost_easy > 0


def test_mastery_update_wrong_on_easy_hurts_more():
    """Incorrect answer on easy question drops mastery more than on hard question."""
    initial = 0.5
    drop_easy = initial - compute_mastery_update(initial, is_correct=False, difficulty="easy")
    drop_medium = initial - compute_mastery_update(initial, is_correct=False, difficulty="medium")
    drop_hard = initial - compute_mastery_update(initial, is_correct=False, difficulty="hard")

    assert drop_easy > drop_medium > drop_hard > 0


def test_mastery_update_boundary_clipping():
    """Mastery never exceeds 1.0 or falls below 0.0."""
    assert compute_mastery_update(0.98, is_correct=True, difficulty="hard") <= 1.0
    assert compute_mastery_update(0.02, is_correct=False, difficulty="easy") >= 0.0


def test_forgetting_decay_grace_period():
    """Topics practiced within 7 days do not decay."""
    now = datetime.now(timezone.utc)
    updated_3_days_ago = now - timedelta(days=3)
    updated_7_days_ago = now - timedelta(days=7)

    assert apply_forgetting_decay(0.8, updated_3_days_ago, current_time=now) == 0.8
    assert apply_forgetting_decay(0.8, updated_7_days_ago, current_time=now) == 0.8


def test_forgetting_decay_after_threshold():
    """Topics not practiced for 7+ days decay with factor 0.95^(days - 7)."""
    now = datetime.now(timezone.utc)
    updated_10_days_ago = now - timedelta(days=10)  # 3 days decayed: 0.95^3

    initial_m = 0.8
    expected = round(initial_m * (0.95 ** 3), 4)
    decayed = apply_forgetting_decay(initial_m, updated_10_days_ago, current_time=now)

    assert decayed == expected
    assert decayed < initial_m
