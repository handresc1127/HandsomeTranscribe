"""
Speaker management for voice identification and recognition.

This module handles speaker matching using voice embeddings,
speaker profile management, and avatar generation.
"""

import hashlib
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple
import random

from .models import SpeakerProfile, SpeakerMatch
from .database import Database
from .exceptions import SpeakerError
from .constants import (
    SPEAKER_MATCH_AUTO_THRESHOLD,
    SPEAKER_MATCH_REVIEW_THRESHOLD
)


class SpeakerManager:
    """Manages speaker profiles and voice embedding matching."""
    
    def __init__(self, database: Database):
        """
        Initialize speaker manager.
        
        Args:
            database: Database instance for persistence
        """
        self.database = database
        self._avatar_colors = [
            "#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6",
            "#1abc9c", "#e67e22", "#34495e", "#16a085", "#27ae60",
            "#2980b9", "#8e44ad", "#c0392b", "#d35400", "#7f8c8d"
        ]
    
    def match_speaker(
        self,
        embedding: np.ndarray,
        threshold_auto: float = SPEAKER_MATCH_AUTO_THRESHOLD,
        threshold_review: float = SPEAKER_MATCH_REVIEW_THRESHOLD
    ) -> SpeakerMatch:
        """
        Match a voice embedding to existing speakers or create new.
        
        Matching logic:
        - confidence >= threshold_auto (98%): auto-identify existing speaker
        - threshold_review <= confidence < threshold_auto (60-98%): mark for manual review
        - confidence < threshold_review (60%): create new speaker
        
        Args:
            embedding: Voice embedding vector to match
            threshold_auto: Threshold for automatic identification (default 0.98)
            threshold_review: Threshold for manual review (default 0.60)
            
        Returns:
            SpeakerMatch object with confidence, speaker_id, and is_new flag
        """
        # Get all speakers with embeddings
        speakers = self.database.get_all_speakers()
        
        best_match = None
        best_confidence = 0.0
        
        # Find best matching speaker
        for speaker in speakers:
            if speaker.voice_embedding_blob:
                stored_embedding = np.frombuffer(
                    speaker.voice_embedding_blob,
                    dtype=np.float32
                )
                confidence = self._cosine_similarity(embedding, stored_embedding)
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = speaker
        
        # Auto-identify if confidence is high enough
        if best_match and best_confidence >= threshold_auto:
            # Update last_seen
            self.database.update_speaker(
                best_match.id,
                last_seen=datetime.now()
            )
            return SpeakerMatch(
                confidence=best_confidence,
                speaker_id=best_match.id,
                is_new=False
            )
        
        # Manual review needed if confidence is moderate
        if best_match and best_confidence >= threshold_review:
            # Don't auto-create, return match for review
            return SpeakerMatch(
                confidence=best_confidence,
                speaker_id=best_match.id,
                is_new=False
            )
        
        # Create new speaker if confidence is too low
        new_speaker = self._create_new_speaker(embedding)
        return SpeakerMatch(
            confidence=0.0,  # New speaker has no match
            speaker_id=new_speaker.id,
            is_new=True
        )
    
    def enrich_embedding(self, speaker_id: int, new_embedding: np.ndarray):
        """
        Enrich an existing speaker's embedding by averaging with new embedding.
        
        This improves speaker recognition over time by incorporating new voice samples.
        
        Args:
            speaker_id: Speaker ID to enrich
            new_embedding: New voice embedding to incorporate
        """
        speaker = self.database.get_speaker(speaker_id)
        if not speaker:
            raise SpeakerError(f"Speaker {speaker_id} not found")
        
        if not speaker.voice_embedding_blob:
            # No existing embedding, just store the new one
            enriched_embedding = new_embedding
        else:
            # Average the embeddings
            existing_embedding = np.frombuffer(
                speaker.voice_embedding_blob,
                dtype=np.float32
            )
            enriched_embedding = (existing_embedding + new_embedding) / 2.0
            # Normalize
            enriched_embedding = enriched_embedding / np.linalg.norm(enriched_embedding)
        
        # Update database
        self.database.update_speaker(
            speaker_id,
            voice_embedding=enriched_embedding.astype(np.float32).tobytes(),
            last_seen=datetime.now()
        )
    
    def create_speaker(
        self,
        name: str,
        embedding: Optional[np.ndarray] = None,
        avatar: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> SpeakerProfile:
        """
        Manually create a new speaker profile.
        
        Args:
            name: Speaker name
            embedding: Optional voice embedding
            avatar: Optional avatar path
            tags: Optional list of tags
            
        Returns:
            Created SpeakerProfile
        """
        # Generate avatar if not provided
        if avatar is None:
            avatar = self._generate_avatar_path(name)
        
        speaker = SpeakerProfile(
            id=-1,  # Will be set by database
            name=name,
            avatar_path=avatar,
            voice_embedding_blob=embedding.astype(np.float32).tobytes() if embedding is not None else None,
            tags=tags or [],
            created_at=datetime.now(),
            last_seen=datetime.now() if embedding is not None else None
        )
        
        speaker.id = self.database.create_speaker(speaker)
        return speaker
    
    def get_all_speakers(self) -> List[SpeakerProfile]:
        """
        Get all speaker profiles.
        
        Returns:
            List of all SpeakerProfile objects
        """
        return self.database.get_all_speakers()
    
    def update_speaker(
        self,
        speaker_id: int,
        name: Optional[str] = None,
        avatar_path: Optional[str] = None,
        tags: Optional[List[str]] = None
    ):
        """
        Update speaker profile.
        
        Args:
            speaker_id: Speaker ID to update
            name: Optional new name
            avatar_path: Optional new avatar path
            tags: Optional new tags list
        """
        updates = {}
        if name is not None:
            updates["name"] = name
        if avatar_path is not None:
            updates["avatar_path"] = avatar_path
        if tags is not None:
            updates["tags"] = tags
        
        if updates:
            self.database.update_speaker(speaker_id, **updates)
    
    def delete_speaker(self, speaker_id: int):
        """
        Delete a speaker profile.
        
        Args:
            speaker_id: Speaker ID to delete
        """
        self.database.delete_speaker(speaker_id)
    
    def _create_new_speaker(self, embedding: np.ndarray) -> SpeakerProfile:
        """
        Internal method to create a new speaker with auto-generated name and avatar.
        
        Args:
            embedding: Voice embedding for the new speaker
            
        Returns:
            Created SpeakerProfile
        """
        # Generate unique speaker name
        existing_speakers = self.database.get_all_speakers()
        speaker_number = len(existing_speakers) + 1
        name = f"Speaker {speaker_number}"
        
        # Ensure unique name
        existing_names = {s.name for s in existing_speakers}
        while name in existing_names:
            speaker_number += 1
            name = f"Speaker {speaker_number}"
        
        # Generate avatar
        avatar_path = self._generate_avatar_path(name)
        
        speaker = SpeakerProfile(
            id=-1,  # Will be set by database
            name=name,
            avatar_path=avatar_path,
            voice_embedding_blob=embedding.astype(np.float32).tobytes(),
            tags=[],
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        speaker.id = self.database.create_speaker(speaker)
        return speaker
    
    def _generate_avatar_path(self, name: str) -> str:
        """
        Generate an avatar identifier for a speaker.
        
        This creates a simple avatar representation using initials and color.
        The actual avatar rendering will be done by the UI.
        
        Args:
            name: Speaker name
            
        Returns:
            Avatar identifier string (format: "initials:color")
        """
        # Extract initials
        parts = name.strip().split()
        if len(parts) >= 2:
            initials = f"{parts[0][0]}{parts[-1][0]}".upper()
        elif len(parts) == 1:
            initials = parts[0][:2].upper()
        else:
            initials = "?"
        
        # Select color deterministically based on name
        name_hash = int(hashlib.md5(name.encode()).hexdigest(), 16)
        color = self._avatar_colors[name_hash % len(self._avatar_colors)]
        
        return f"{initials}:{color}"
    
    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            a: First vector
            b: Second vector
            
        Returns:
            Cosine similarity (0 to 1)
        """
        # Normalize vectors
        a_norm = a / np.linalg.norm(a)
        b_norm = b / np.linalg.norm(b)
        # Calculate dot product
        return float(np.dot(a_norm, b_norm))
