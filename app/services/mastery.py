"""
Topic mastery calculation and forgetting decay engine.

Formulas:
1. Exponentially Weighted Update:
   M_new = M_old + alpha * w_d * (outcome - M_old)
   where:
     - alpha = 0.15 (learning rate)
     - outcome = 1.0 if correct else 0.0
     - w_d:
         easy:   correct=0.6, incorrect=1.4  (wrong on easy drops mastery more)
         medium: correct=1.0, incorrect=1.0  (balanced)
         hard:   correct=1.4, incorrect=0.6  (correct on hard boosts mastery more)
     - clipped to [0.0, 1.0]

2. Forgetting Decay:
   Topics not practiced in 7+ days decay lazily:
   M_decayed = M_current * (0.95) ** (days_inactive - 7)
"""

from datetime import datetime, timezone
from typing import Optional

ALPHA = 0.15

# Difficulty weights: (weight_if_correct, weight_if_incorrect)
DIFFICULTY_WEIGHTS = {
    "easy": (0.6, 1.4),
    "medium": (1.0, 1.0),
    "hard": (1.4, 0.6),
}


def compute_mastery_update(
    current_mastery: float,
    is_correct: bool,
    difficulty: str = "medium",
    alpha: float = ALPHA,
) -> float:
    """
    Compute updated mastery after answering a question.

    Args:
        current_mastery: Current mastery level (0.0 to 1.0).
        is_correct: Whether the question was answered correctly.
        difficulty: 'easy', 'medium', or 'hard'.
        alpha: Learning rate.

    Returns:
        New mastery float clipped to [0.0, 1.0].
    """
    diff_key = difficulty.lower() if difficulty else "medium"
    w_correct, w_incorrect = DIFFICULTY_WEIGHTS.get(diff_key, (1.0, 1.0))
    w_d = w_correct if is_correct else w_incorrect
    outcome = 1.0 if is_correct else 0.0

    new_mastery = current_mastery + alpha * w_d * (outcome - current_mastery)
    # Clip between 0.0 and 1.0, rounded to 4 decimals
    return round(max(0.0, min(1.0, new_mastery)), 4)


def apply_forgetting_decay(
    mastery: float,
    last_updated: datetime,
    current_time: Optional[datetime] = None,
    decay_rate: float = 0.95,
    threshold_days: int = 7,
) -> float:
    """
    Apply forgetting decay if a topic hasn't been practiced for 7+ days.

    Args:
        mastery: Stored mastery value (0.0 to 1.0).
        last_updated: Timestamp when mastery was last updated.
        current_time: Current timestamp (defaults to UTC now).
        decay_rate: Daily decay factor (default 0.95).
        threshold_days: Grace period before decay starts (default 7 days).

    Returns:
        Decayed mastery float clipped to [0.0, 1.0].
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)

    # Ensure timezone awareness
    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    delta_days = (current_time - last_updated).total_seconds() / 86400.0

    if delta_days <= threshold_days:
        return mastery

    inactive_days = delta_days - threshold_days
    decayed = mastery * (decay_rate ** inactive_days)
    return round(max(0.0, min(1.0, decayed)), 4)
