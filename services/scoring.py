from __future__ import annotations

from dataclasses import dataclass

from config import settings


@dataclass(frozen=True, slots=True)
class ScoreRules:
    exact_score: int = settings.exact_score_points
    correct_outcome: int = settings.outcome_points
    wrong: int = settings.wrong_points


DEFAULT_RULES = ScoreRules()


def outcome(home: int, away: int) -> str:
    if home > away:
        return "HOME"
    if home < away:
        return "AWAY"
    return "DRAW"


def calculate_prediction_points(
    predicted_home: int,
    predicted_away: int,
    actual_home: int,
    actual_away: int,
    rules: ScoreRules = DEFAULT_RULES,
) -> int:
    if predicted_home == actual_home and predicted_away == actual_away:
        return rules.exact_score
    if outcome(predicted_home, predicted_away) == outcome(actual_home, actual_away):
        return rules.correct_outcome
    return rules.wrong


def is_outcome_consistent(predicted_home: int, predicted_away: int, selected_outcome: str) -> bool:
    return outcome(predicted_home, predicted_away) == selected_outcome
