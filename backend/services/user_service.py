"""
User Service for Korean Real Estate RAG AI Chatbot
Handles user-related business logic with Supabase integration
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from supabase import Client

from core.database import get_supabase_client, execute_supabase_operation

logger = logging.getLogger(__name__)


class UserService:
    """Service for user-related operations using Supabase"""

    def __init__(self):
        self.supabase: Client | None = None
        
    async def _get_client(self) -> Client:
        """Get Supabase client"""
        if self.supabase is None:
            self.supabase = get_supabase_client()
        return self.supabase
    async def get_primary_profile(self, user_id: str) -> dict[str, Any] | None:
        """Get user's primary profile from Supabase"""
        try:
            logger.info(f"Getting primary profile for user: {user_id}")
            
            def query_profile(client: Client) -> dict | None:
                response = client.table('user_profiles').select('*').eq('user_id', user_id).execute()
                return response.data[0] if response.data else None
            
            profile_data = await execute_supabase_operation(query_profile)
            
            return profile_data

        except Exception as e:
            logger.error(f"User profile lookup failed: {str(e)}")
            return None

    async def get_conversation_history(
        self, user_id: str, conversation_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get conversation history from Supabase"""
        try:
            logger.info(
                f"Getting conversation history for user: {user_id}, conversation: {conversation_id}"
            )
            
            def query_history(client: Client) -> list[dict]:
                response = (
                    client.table('conversation_history')
                    .select('*')
                    .eq('user_id', user_id)
                    .eq('conversation_id', conversation_id)
                    .order('created_at', desc=True)
                    .limit(limit)
                    .execute()
                )
                return response.data or []
            
            return await execute_supabase_operation(query_history)
        except Exception as e:
            logger.error(f"Conversation history lookup failed: {str(e)}")
            return []

    async def save_conversation_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        intent: str | None = None,
        entities: dict[str, Any] | None = None,
        search_results: list[str] | None = None,
        recommended_policies: list[str] | None = None,
        confidence_score: float | None = None,
        model_used: str | None = None,
    ) -> bool:
        """Save conversation message to Supabase"""
        try:
            logger.info(f"Saving conversation message for user: {user_id}")
            
            message_data = {
                'id': str(uuid.uuid4()),
                'user_id': user_id,
                'conversation_id': conversation_id,
                'role': role,
                'content': content,
                'intent': intent,
                'entities': entities or {},
                'search_results': search_results or [],
                'recommended_policies': recommended_policies or [],
                'confidence_score': confidence_score,
                'model_used': model_used,
                'created_at': datetime.utcnow().isoformat()
            }
            
            def insert_message(client: Client) -> bool:
                response = client.table('conversation_history').insert(message_data).execute()
                return len(response.data) > 0
            
            success = await execute_supabase_operation(insert_message)
            
            if success:
                logger.info(f"Successfully saved conversation message for user: {user_id}")
            else:
                logger.warning(f"Failed to save conversation message for user: {user_id}")
                
            return success

        except Exception as e:
            logger.error(f"Conversation message saving failed: {str(e)}")
            return False

    async def create_or_update_user_profile(
        self, 
        user_id: str, 
        profile_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Create or update user profile in Supabase"""
        try:
            logger.info(f"Creating/updating user profile for user: {user_id}")
            
            # Prepare profile data
            profile_record = {
                'user_id': user_id,
                'age': profile_data.get('age'),
                'income': profile_data.get('income'),
                'region': profile_data.get('region'),
                'property_type': profile_data.get('property_type'),
                'transaction_type': profile_data.get('transaction_type'),
                'budget_min': profile_data.get('budget_min'),
                'budget_max': profile_data.get('budget_max'),
                'room_count': profile_data.get('room_count'),
                'area': profile_data.get('area'),
                'additional_preferences': profile_data.get('additional_preferences', {}),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            def upsert_profile(client: Client) -> dict:
                response = (
                    client.table('user_profiles')
                    .upsert(profile_record)
                    .execute()
                )
                return response.data[0] if response.data else None
            
            return await execute_supabase_operation(upsert_profile)

        except Exception as e:
            logger.error(f"User profile create/update failed: {str(e)}")
            return None
