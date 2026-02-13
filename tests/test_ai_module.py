"""Tests for ai_module (AI-powered recommendations for new users).

Covers guided questions, prompt building, and AI recommendations engine.

Part of the Smart Cloud Optimizer graduation project.
"""

import json
from unittest.mock import Mock, patch

import pytest

from ai_module import get_ai_recommendations, build_prompt, get_guided_questions


# ---------------------------------------------------------------------------
# Guided Questions Tests
# ---------------------------------------------------------------------------

class TestGuidedQuestions:

    def test_returns_list(self):
        """get_guided_questions should return a list."""
        questions = get_guided_questions()
        assert isinstance(questions, list)
        assert len(questions) > 0

    def test_each_question_has_required_keys(self):
        """Each question dict must have id, question, options keys."""
        questions = get_guided_questions()
        for q in questions:
            assert "id" in q
            assert "question" in q
            assert "options" in q
            assert isinstance(q["id"], str)
            assert isinstance(q["question"], str)
            assert isinstance(q["options"], list)

    def test_has_all_required_question_ids(self):
        """Must have all 9 question IDs expected by the system."""
        questions = get_guided_questions()
        ids = {q["id"] for q in questions}

        required_ids = {
            "business_type",
            "expected_users",
            "uptime_requirement",
            "priority",
            "traffic_pattern",
            "availability",
            "monthly_budget",
            "experience_level",
            "extra_notes"
        }

        assert ids == required_ids, f"Missing IDs: {required_ids - ids}, Extra: {ids - required_ids}"

    def test_extra_notes_has_empty_options(self):
        """extra_notes question should have empty options (rendered as text area)."""
        questions = get_guided_questions()
        extra_notes = next(q for q in questions if q["id"] == "extra_notes")
        assert extra_notes["options"] == []


# ---------------------------------------------------------------------------
# Prompt Builder Tests
# ---------------------------------------------------------------------------

class TestPromptBuilder:

    def test_builds_prompt_from_answers(self):
        """build_prompt should return a string containing all answer values."""
        answers = {
            "business_type": "Web application",
            "expected_users": "1,000-10,000",
            "uptime_requirement": "24x7 (always on)",
            "priority": "Balance cost and performance",
            "traffic_pattern": "Predictable daily peaks",
            "availability": "Must be highly available",
            "monthly_budget": "$500-2,000",
            "experience_level": "Intermediate",
            "extra_notes": "Must use us-west-2"
        }

        prompt = build_prompt(answers)

        assert isinstance(prompt, str)
        assert "Web application" in prompt
        assert "1,000-10,000" in prompt
        assert "24x7" in prompt
        assert "Balance cost and performance" in prompt
        assert "Predictable daily peaks" in prompt
        assert "Must be highly available" in prompt
        assert "$500-2,000" in prompt
        assert "Intermediate" in prompt
        assert "us-west-2" in prompt

    def test_handles_missing_optional_fields(self):
        """build_prompt should handle missing optional fields gracefully."""
        answers = {
            "business_type": "E-commerce",
            "priority": "Minimize cost",
            "traffic_pattern": "Stable",
            "availability": "Can tolerate downtime",
            "experience_level": "Beginner"
        }

        prompt = build_prompt(answers)

        assert "E-commerce" in prompt
        assert "Minimize cost" in prompt
        assert "Not specified" in prompt  # For missing fields

    def test_specifies_json_output_format(self):
        """Prompt should specify the expected JSON structure."""
        answers = {
            "business_type": "Mobile backend",
            "priority": "Maximize performance",
            "traffic_pattern": "Highly variable",
            "availability": "Must be highly available",
            "experience_level": "Advanced"
        }

        prompt = build_prompt(answers)

        assert "recommended_setup" in prompt
        assert "estimated_cost" in prompt
        assert "explanation" in prompt
        assert "JSON" in prompt


# ---------------------------------------------------------------------------
# AI Recommender Tests
# ---------------------------------------------------------------------------

class TestAIRecommender:

    @patch("ai_module.recommender.genai.Client")
    @patch("ai_module.recommender.config.GOOGLE_API_KEY", "test-key-123")
    def test_successful_api_call(self, mock_client_class):
        """get_ai_recommendations should parse valid JSON response."""
        # Mock API response
        mock_response = Mock()
        mock_response.text = '''
        Here's the recommendation:
        {
            "recommended_setup": {
                "compute": "Lambda + API Gateway",
                "database": "DynamoDB",
                "storage": "S3"
            },
            "estimated_cost": 150.25,
            "explanation": "Serverless architecture for cost efficiency"
        }
        Some extra text after
        '''

        # Mock the new Client-based API
        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        prompt = "Design an architecture"
        parsed, raw = get_ai_recommendations(prompt)

        assert "error" not in parsed
        assert parsed["estimated_cost"] == 150.25
        assert "Lambda" in parsed["recommended_setup"]["compute"]
        assert raw == mock_response.text.strip()

    @patch("ai_module.recommender.genai.Client")
    @patch("ai_module.recommender.config.GOOGLE_API_KEY", "test-key-123")
    def test_handles_api_exception(self, mock_client_class):
        """get_ai_recommendations should return error dict on API failure."""
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("Network error")
        mock_client_class.return_value = mock_client

        parsed, raw = get_ai_recommendations("test prompt")

        assert "error" in parsed
        assert "Network error" in parsed["error"]
        assert raw == ""

    @patch("ai_module.recommender.genai.Client")
    @patch("ai_module.recommender.config.GOOGLE_API_KEY", "test-key-123")
    def test_handles_invalid_json(self, mock_client_class):
        """get_ai_recommendations should return error dict on malformed JSON."""
        mock_response = Mock()
        mock_response.text = "This is not JSON at all, just plain text"

        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        parsed, raw = get_ai_recommendations("test prompt")

        assert "error" in parsed
        assert "JSON" in parsed["error"] or "valid" in parsed["error"]

    @patch("ai_module.recommender.config.GOOGLE_API_KEY", "")
    def test_missing_api_key(self):
        """get_ai_recommendations should return error if API key not set."""
        parsed, raw = get_ai_recommendations("test prompt")

        assert "error" in parsed
        assert "GOOGLE_API_KEY" in parsed["error"]
        assert raw == ""

    @patch("ai_module.recommender.genai.Client")
    @patch("ai_module.recommender.config.GOOGLE_API_KEY", "test-key-123")
    def test_empty_response(self, mock_client_class):
        """get_ai_recommendations should handle empty API response."""
        mock_response = Mock()
        mock_response.text = ""

        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        parsed, raw = get_ai_recommendations("test prompt")

        assert "error" in parsed
