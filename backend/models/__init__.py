"""
Data models for Korean Real Estate RAG AI Chatbot
"""

from .property import Property, PropertyFilter, PropertySearchResult
from .user import User, UserProfile, ConversationHistory
from .policy import GovernmentPolicy, PolicyMatch
from .base import Base

__all__ = [
    "Base",
    "Property",
    "PropertyFilter", 
    "PropertySearchResult",
    "User",
    "UserProfile",
    "ConversationHistory",
    "GovernmentPolicy",
    "PolicyMatch",
]