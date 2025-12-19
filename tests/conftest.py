import pytest
import os
from unittest.mock import MagicMock
from sqlite_utils import Database
from src.schema import VideoAnalysis

@pytest.fixture
def mock_gemini_response(monkeypatch):
    """Mocks the Gemini API response."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    
    # Sample JSON that strictly follows our schema
    sample_analysis = {
        "visual_grounding": {
            "detected_entities": ["Teacher", "Whiteboard", "Robot Kit"],
            "setting": "Classroom",
            "text_on_screen": "Robotics 101"
        },
        "summary": "This is a mocked summary of a safe video.",
        "video_metadata": {
            "format": "Standard_Landscape",
            "duration_perceived": "Medium (5-20 min)"
        },
        "content_taxonomy": {
            "primary_genre": "Education_STEM",
            "specific_topic": "Robotics",
            "target_demographic": "Child (5-9)"
        },
        "narrative_quality": {
            "structural_integrity": "Coherent_Narrative",
            "creative_intent": "Informational",
            "weirdness_verdict": "Normal"
        },
        "risk_assessment": {
            "safety_score": 95,
            "flags": {
                "ideological_radicalization": False,
                "pseudoscience_misinfo": False,
                "body_image_harm": False,
                "dangerous_behavior": False,
                "commercial_exploitation": False,
                "lootbox_gambling": False,
                "sexual_themes": False,
                "mascot_horror": False
            }
        },
        "cognitive_nutrition": {
            "intellectual_density": "High (Educational)",
            "emotional_volatility": "Calm",
            "is_brainrot": False,
            "is_slop": False
        },
        "verdict": {
            "action": "Approve",
            "reason": "Safe educational content."
        }
    }
    
    mock_response.text = VideoAnalysis(**sample_analysis).model_dump_json()
    mock_response.usage_metadata.prompt_token_count = 100
    mock_response.usage_metadata.candidates_token_count = 50
    
    mock_client.models.generate_content.return_value = mock_response
    
    # Mocking the client initialization (bit harder in analyze.py main loop likely via dependency injection or simple monkeypatch of genai.Client)
    # For unit testing specific functions, we pass the mock.
    
    return mock_client

@pytest.fixture
def temp_db(tmp_path):
    """Creates a temporary SQLite database."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    # Create tables
    db["videos"].create({
        "video_id": str,
        "title": str,
        "video_url": str,
        "channel_name": str,
        "watch_timestamp": str, 
        "status": str,
        "safety_score": int,
        "primary_genre": str,
        "is_slop": bool,
        "is_brainrot": bool,
        "is_short": bool,
        "analysis_json": str,
         "model_used": str,
         "input_tokens": int,
         "output_tokens": int
    }, pk="video_id")
    return db
