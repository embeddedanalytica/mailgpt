"""Unit tests for recommendation contract v1."""

import unittest

from recommendation_contract import (
    CONTRACT_VERSION_V1,
    AthleteState,
    Recommendation,
    RecommendationContext,
    RecommendationContractError,
    validate_athlete_state,
    validate_recommendation,
    validate_recommendation_context,
)


def _valid_state() -> AthleteState:
    return AthleteState(
        athlete_id="ath_123",
        email="user@example.com",
        goal="Improve 10k pace",
        current_plan_summary="Week 3 build phase",
        current_plan_version=2,
        recent_activity_summary="4 runs, 1 strength session, no missed workouts.",
        window_days=14,
        generated_at_epoch=1735732800,
        last_recommendation_text="Keep easy runs easy this week.",
        last_recommendation_epoch=1735646400,
    )


def _valid_recommendation() -> Recommendation:
    return Recommendation(
        recommendation_text="Keep the next two runs easy and add one short tempo block.",
        why="Recent load increased and fatigue markers are moderate.",
        confidence=0.78,
        risk_flags=["fatigue_trend"],
        next_check_in_days=3,
        focus_area="load_management",
        evidence_window_days=14,
        prompt_version="rec_prompt_v1",
    )


class TestAthleteStateValidation(unittest.TestCase):
    def test_valid_state_passes(self):
        state = _valid_state()
        validate_athlete_state(state)

    def test_invalid_window_days_fails(self):
        state = _valid_state()
        with self.assertRaises(RecommendationContractError):
            validate_athlete_state(
                AthleteState(
                    **{**state.to_dict(), "window_days": 30}
                )
            )

    def test_empty_athlete_id_fails(self):
        state = _valid_state()
        with self.assertRaises(RecommendationContractError):
            validate_athlete_state(
                AthleteState(
                    **{**state.to_dict(), "athlete_id": ""}
                )
            )


class TestRecommendationValidation(unittest.TestCase):
    def test_valid_recommendation_passes(self):
        rec = _valid_recommendation()
        validate_recommendation(rec)

    def test_confidence_out_of_range_fails(self):
        rec = _valid_recommendation()
        with self.assertRaises(RecommendationContractError):
            validate_recommendation(
                Recommendation(
                    **{**rec.to_dict(), "confidence": 1.5}
                )
            )

    def test_invalid_evidence_window_fails(self):
        rec = _valid_recommendation()
        with self.assertRaises(RecommendationContractError):
            validate_recommendation(
                Recommendation(
                    **{**rec.to_dict(), "evidence_window_days": 21}
                )
            )

    def test_empty_recommendation_text_fails(self):
        rec = _valid_recommendation()
        with self.assertRaises(RecommendationContractError):
            validate_recommendation(
                Recommendation(
                    **{**rec.to_dict(), "recommendation_text": "   "}
                )
            )


class TestRecommendationContextValidation(unittest.TestCase):
    def test_valid_context_passes(self):
        context = RecommendationContext(
            state=_valid_state(),
            recommendation=_valid_recommendation(),
            model_name="gpt-5-nano",
            created_at_epoch=1735732801,
            correlation_id="req-abc-123",
            contract_version=CONTRACT_VERSION_V1,
        )
        validate_recommendation_context(context)

    def test_invalid_contract_version_fails(self):
        context = RecommendationContext(
            state=_valid_state(),
            recommendation=_valid_recommendation(),
            model_name="gpt-5-nano",
            created_at_epoch=1735732801,
            correlation_id="req-abc-123",
            contract_version="v2",
        )
        with self.assertRaises(RecommendationContractError):
            validate_recommendation_context(context)

    def test_round_trip_serialization(self):
        original = RecommendationContext(
            state=_valid_state(),
            recommendation=_valid_recommendation(),
            model_name="gpt-5-nano",
            created_at_epoch=1735732801,
            correlation_id="req-abc-123",
            contract_version=CONTRACT_VERSION_V1,
        )
        payload = original.to_dict()
        rebuilt = RecommendationContext.from_dict(payload)
        self.assertEqual(rebuilt.to_dict(), payload)


if __name__ == "__main__":
    unittest.main()
