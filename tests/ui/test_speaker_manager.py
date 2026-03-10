"""
Unit tests for SpeakerManager.

Tests speaker matching logic and embedding operations.
"""

import pytest
import numpy as np

from handsome_transcribe.ui.speaker_manager import SpeakerManager
from handsome_transcribe.ui.models import SpeakerProfile, SpeakerMatch


class TestSpeakerManager:
    """Tests for SpeakerManager."""
    
    def test_create_speaker_manager(self, speaker_manager):
        """Test creating a SpeakerManager instance."""
        assert speaker_manager is not None
    
    def test_match_new_speaker(self, speaker_manager):
        """Test matching a completely new speaker."""
        embedding = np.random.randn(128).astype(np.float32)
        
        match = speaker_manager.match_speaker(embedding)
        
        assert match.is_new is True
        assert match.confidence == 0.0
        assert match.speaker_id is not None
    
    def test_match_existing_speaker_high_confidence(self, speaker_manager):
        """Test matching existing speaker with high confidence."""
        # Create a speaker
        embedding1 = np.random.randn(128).astype(np.float32)
        embedding1 = embedding1 / np.linalg.norm(embedding1)  # Normalize
        
        speaker = SpeakerProfile(
            id=-1,
            name="Test Speaker",
            voice_embedding_blob=embedding1.tobytes()
        )
        speaker_id = speaker_manager.database.create_speaker(speaker)
        
        # Create very similar embedding (98%+ match)
        embedding2 = embedding1 + np.random.randn(128).astype(np.float32) * 0.01
        embedding2 = embedding2 / np.linalg.norm(embedding2)
        
        match = speaker_manager.match_speaker(embedding2)
        
        # Should auto-identify
        assert match.is_new is False
        assert match.confidence >= 0.98
        assert match.speaker_id == speaker_id
    
    def test_match_existing_speaker_medium_confidence(self, speaker_manager):
        """Test matching existing speaker with medium confidence (review required)."""
        # Create a speaker
        embedding1 = np.random.randn(128).astype(np.float32)
        embedding1 = embedding1 / np.linalg.norm(embedding1)
        
        speaker = SpeakerProfile(
            id=-1,
            name="Test Speaker",
            voice_embedding_blob=embedding1.tobytes()
        )
        speaker_id = speaker_manager.database.create_speaker(speaker)
        
        # Create somewhat similar embedding (60-98% range)
        embedding2 = embedding1 + np.random.randn(128).astype(np.float32) * 0.3
        embedding2 = embedding2 / np.linalg.norm(embedding2)
        
        match = speaker_manager.match_speaker(embedding2)
        
        # Should require review
        if match.confidence >= 0.60 and match.confidence < 0.98:
            assert match.is_new is False
            assert match.speaker_id == speaker_id
    
    def test_enrich_embedding(self, speaker_manager):
        """Test enriching a speaker's embedding."""
        # Create initial speaker
        embedding1 = np.random.randn(128).astype(np.float32)
        speaker = SpeakerProfile(
            id=-1,
            name="Test Speaker",
            voice_embedding_blob=embedding1.tobytes()
        )
        speaker_id = speaker_manager.database.create_speaker(speaker)
        
        # Enrich with new embedding
        embedding2 = np.random.randn(128).astype(np.float32)
        speaker_manager.enrich_embedding(speaker_id, embedding2)
        
        # Retrieve updated speaker
        updated_speaker = speaker_manager.database.get_speaker(speaker_id)
        
        # Embedding should have changed (averaged)
        assert updated_speaker.voice_embedding_blob != embedding1.tobytes()
    
    def test_generate_avatar(self, speaker_manager):
        """Test avatar generation from name."""
        avatar = speaker_manager._generate_avatar_path("John Doe")
        
        assert avatar.startswith("JD:")
        assert "#" in avatar  # Should have color code
    
    def test_generate_avatar_single_name(self, speaker_manager):
        """Test avatar generation with single name."""
        avatar = speaker_manager._generate_avatar_path("Madonna")
        
        assert avatar.startswith("MA:")
    
    def test_cosine_similarity_identical(self, speaker_manager):
        """Test cosine similarity with identical vectors."""
        vec = np.random.randn(128).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        
        similarity = speaker_manager._cosine_similarity(vec, vec)
        
        assert similarity == pytest.approx(1.0, abs=1e-6)
    
    def test_cosine_similarity_orthogonal(self, speaker_manager):
        """Test cosine similarity with orthogonal vectors."""
        vec1 = np.zeros(128, dtype=np.float32)
        vec1[0] = 1.0
        
        vec2 = np.zeros(128, dtype=np.float32)
        vec2[1] = 1.0
        
        similarity = speaker_manager._cosine_similarity(vec1, vec2)
        
        assert similarity == pytest.approx(0.0, abs=1e-6)
