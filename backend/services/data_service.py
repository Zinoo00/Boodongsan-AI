"""
Data Service for Korean Real Estate RAG AI Chatbot
Unified service for managing properties and policies data with Supabase integration

이 서비스는 PropertyService와 PolicyService를 대체하며,
Supabase를 통해 부동산 및 정책 데이터를 관리합니다.
"""

import logging
from datetime import datetime
from typing import Any

from supabase import Client

from core.database import execute_supabase_operation, get_supabase_client

logger = logging.getLogger(__name__)


class DataService:
    """
    Unified service for properties and policies data management

    Manages:
    - Properties (부동산 매물)
    - Government policies (정부 지원 정책)
    """

    def __init__(self):
        self.supabase: Client | None = None

    async def _get_client(self) -> Client:
        """Get Supabase client"""
        if self.supabase is None:
            self.supabase = get_supabase_client()
        return self.supabase

    # ==================== Property Methods ====================

    async def create_property(self, property_data: dict[str, Any]) -> dict[str, Any] | None:
        """
        Create a new property listing

        Args:
            property_data: Property information (address, price, type, etc.)

        Returns:
            Created property data or None if failed
        """
        try:
            logger.info(f"Creating property: {property_data.get('address')}")

            def insert_property(client: Client) -> dict:
                response = client.table("properties").insert(property_data).execute()
                return response.data[0] if response.data else None

            result = await execute_supabase_operation(insert_property)

            if result:
                logger.info(f"✅ Property created: {result.get('id')}")
            return result

        except Exception as e:
            logger.error(f"❌ Property creation failed: {str(e)}")
            return None

    async def get_property(self, property_id: str) -> dict[str, Any] | None:
        """Get property by ID"""
        try:

            def query_property(client: Client) -> dict | None:
                response = (
                    client.table("properties").select("*").eq("id", property_id).execute()
                )
                return response.data[0] if response.data else None

            return await execute_supabase_operation(query_property)

        except Exception as e:
            logger.error(f"❌ Property lookup failed: {str(e)}")
            return None

    async def search_properties(
        self, filters: dict[str, Any] | None = None, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        """
        Search properties with filters

        Args:
            filters: Search filters (district, property_type, price_min, etc.)
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of properties matching filters
        """
        try:
            filters = filters or {}
            logger.info(f"Searching properties with filters: {filters}")

            def query_properties(client: Client) -> list[dict]:
                query = client.table("properties").select("*")

                # Apply filters
                if filters.get("district"):
                    query = query.eq("district", filters["district"])
                if filters.get("dong"):
                    query = query.eq("dong", filters["dong"])
                if filters.get("property_type"):
                    query = query.eq("property_type", filters["property_type"])
                if filters.get("transaction_type"):
                    query = query.eq("transaction_type", filters["transaction_type"])

                # Price range
                if filters.get("price_min"):
                    query = query.gte("price", filters["price_min"])
                if filters.get("price_max"):
                    query = query.lte("price", filters["price_max"])

                # Area range
                if filters.get("area_min"):
                    query = query.gte("area_exclusive", filters["area_min"])
                if filters.get("area_max"):
                    query = query.lte("area_exclusive", filters["area_max"])

                # Room count
                if filters.get("room_count"):
                    query = query.eq("room_count", filters["room_count"])

                # Only active listings
                listing_status = filters.get("listing_status", "active")
                query = query.eq("listing_status", listing_status)

                # Pagination
                query = query.range(offset, offset + limit - 1)
                query = query.order("created_at", desc=True)

                response = query.execute()
                return response.data or []

            results = await execute_supabase_operation(query_properties)
            logger.info(f"Found {len(results)} properties")
            return results

        except Exception as e:
            logger.error(f"❌ Property search failed: {str(e)}")
            return []

    async def update_property(
        self, property_id: str, updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Update property data"""
        try:
            updates["updated_at"] = datetime.utcnow().isoformat()

            def update_operation(client: Client) -> dict | None:
                response = (
                    client.table("properties")
                    .update(updates)
                    .eq("id", property_id)
                    .execute()
                )
                return response.data[0] if response.data else None

            result = await execute_supabase_operation(update_operation)

            if result:
                logger.info(f"✅ Property updated: {property_id}")
            return result

        except Exception as e:
            logger.error(f"❌ Property update failed: {str(e)}")
            return None

    async def delete_property(self, property_id: str) -> bool:
        """Delete (soft delete) a property"""
        try:

            def delete_operation(client: Client) -> bool:
                response = (
                    client.table("properties")
                    .update({"listing_status": "hidden", "updated_at": datetime.utcnow().isoformat()})
                    .eq("id", property_id)
                    .execute()
                )
                return len(response.data) > 0

            result = await execute_supabase_operation(delete_operation)

            if result:
                logger.info(f"✅ Property deleted (soft): {property_id}")
            return result

        except Exception as e:
            logger.error(f"❌ Property deletion failed: {str(e)}")
            return False

    # ==================== Policy Methods ====================

    async def create_policy(self, policy_data: dict[str, Any]) -> dict[str, Any] | None:
        """
        Create a new government policy

        Args:
            policy_data: Policy information (name, type, eligibility, etc.)

        Returns:
            Created policy data or None if failed
        """
        try:
            logger.info(f"Creating policy: {policy_data.get('policy_name')}")

            def insert_policy(client: Client) -> dict:
                response = (
                    client.table("government_policies").insert(policy_data).execute()
                )
                return response.data[0] if response.data else None

            result = await execute_supabase_operation(insert_policy)

            if result:
                logger.info(f"✅ Policy created: {result.get('id')}")
            return result

        except Exception as e:
            logger.error(f"❌ Policy creation failed: {str(e)}")
            return None

    async def get_policy(self, policy_id: str) -> dict[str, Any] | None:
        """Get policy by ID"""
        try:

            def query_policy(client: Client) -> dict | None:
                response = (
                    client.table("government_policies")
                    .select("*")
                    .eq("id", policy_id)
                    .execute()
                )
                return response.data[0] if response.data else None

            return await execute_supabase_operation(query_policy)

        except Exception as e:
            logger.error(f"❌ Policy lookup failed: {str(e)}")
            return None

    async def get_all_policies(self, active_only: bool = True) -> list[dict[str, Any]]:
        """
        Get all government policies

        Args:
            active_only: If True, only return active policies

        Returns:
            List of policies
        """
        try:

            def query_policies(client: Client) -> list[dict]:
                query = client.table("government_policies").select("*")

                if active_only:
                    query = query.eq("is_active", True)

                query = query.order("priority", desc=True)
                response = query.execute()
                return response.data or []

            results = await execute_supabase_operation(query_policies)
            logger.info(f"Found {len(results)} policies")
            return results

        except Exception as e:
            logger.error(f"❌ Policy listing failed: {str(e)}")
            return []

    async def search_policies(
        self, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Search policies with filters

        Args:
            filters: Search filters (policy_type, target_demographic, etc.)

        Returns:
            List of matching policies
        """
        try:
            filters = filters or {}
            logger.info(f"Searching policies with filters: {filters}")

            def query_policies(client: Client) -> list[dict]:
                query = client.table("government_policies").select("*")

                # Apply filters
                if filters.get("policy_type"):
                    query = query.eq("policy_type", filters["policy_type"])
                if filters.get("target_demographic"):
                    query = query.eq("target_demographic", filters["target_demographic"])

                # Only active policies
                query = query.eq("is_active", True)
                query = query.order("priority", desc=True)

                response = query.execute()
                return response.data or []

            results = await execute_supabase_operation(query_policies)
            logger.info(f"Found {len(results)} policies")
            return results

        except Exception as e:
            logger.error(f"❌ Policy search failed: {str(e)}")
            return []

    async def match_policies_for_user(
        self, user_profile: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Match policies based on user profile

        Args:
            user_profile: User profile with age, income, region, etc.

        Returns:
            List of eligible policies with eligibility information
        """
        try:
            logger.info(
                f"Matching policies for user: {user_profile.get('user_id', 'unknown')}"
            )

            # Get all active policies
            policies = await self.get_all_policies(active_only=True)

            eligible_policies = []

            for policy in policies:
                # Check eligibility
                is_eligible = True
                eligibility_reasons = []
                eligibility_score = 0.0

                # Age check
                if policy.get("age_min") or policy.get("age_max"):
                    user_age = user_profile.get("age")
                    if user_age:
                        if policy.get("age_min") and user_age < policy["age_min"]:
                            is_eligible = False
                        if policy.get("age_max") and user_age > policy["age_max"]:
                            is_eligible = False
                        if is_eligible:
                            eligibility_reasons.append(f"연령 조건 충족 ({user_age}세)")
                            eligibility_score += 1.0

                # Income check
                if policy.get("income_min") or policy.get("income_max"):
                    user_income = user_profile.get("income")
                    if user_income:
                        if policy.get("income_min") and user_income < policy["income_min"]:
                            is_eligible = False
                        if policy.get("income_max") and user_income > policy["income_max"]:
                            is_eligible = False
                        if is_eligible:
                            eligibility_reasons.append("소득 조건 충족")
                            eligibility_score += 1.0

                # Region check
                if policy.get("available_regions"):
                    user_region = user_profile.get("region")
                    if user_region:
                        if user_region not in policy["available_regions"]:
                            is_eligible = False
                        else:
                            eligibility_reasons.append(f"지역 조건 충족 ({user_region})")
                            eligibility_score += 1.0

                # First-time buyer check
                if policy.get("requires_first_time_buyer"):
                    if not user_profile.get("is_first_time_buyer"):
                        is_eligible = False
                    else:
                        eligibility_reasons.append("생애 최초 구입자 조건 충족")
                        eligibility_score += 1.0

                # Newlywed check
                if policy.get("requires_newlywed"):
                    if not user_profile.get("is_newlywed"):
                        is_eligible = False
                    else:
                        eligibility_reasons.append("신혼부부 조건 충족")
                        eligibility_score += 1.0

                if is_eligible:
                    # Normalize score (0-1)
                    max_possible_score = 5.0  # Adjust based on number of criteria
                    normalized_score = min(eligibility_score / max_possible_score, 1.0)

                    eligible_policies.append(
                        {
                            "policy": policy,
                            "is_eligible": True,
                            "eligibility_score": normalized_score,
                            "eligibility_reasons": eligibility_reasons,
                        }
                    )

            # Sort by eligibility score (highest first)
            eligible_policies.sort(key=lambda x: x["eligibility_score"], reverse=True)

            logger.info(f"✅ Found {len(eligible_policies)} eligible policies")
            return eligible_policies

        except Exception as e:
            logger.error(f"❌ Policy matching failed: {str(e)}")
            return []

    async def update_policy(
        self, policy_id: str, updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Update policy data"""
        try:
            updates["updated_at"] = datetime.utcnow().isoformat()

            def update_operation(client: Client) -> dict | None:
                response = (
                    client.table("government_policies")
                    .update(updates)
                    .eq("id", policy_id)
                    .execute()
                )
                return response.data[0] if response.data else None

            result = await execute_supabase_operation(update_operation)

            if result:
                logger.info(f"✅ Policy updated: {policy_id}")
            return result

        except Exception as e:
            logger.error(f"❌ Policy update failed: {str(e)}")
            return None

    async def deactivate_policy(self, policy_id: str) -> bool:
        """Deactivate a policy (soft delete)"""
        try:

            def deactivate_operation(client: Client) -> bool:
                response = (
                    client.table("government_policies")
                    .update(
                        {
                            "is_active": False,
                            "updated_at": datetime.utcnow().isoformat(),
                        }
                    )
                    .eq("id", policy_id)
                    .execute()
                )
                return len(response.data) > 0

            result = await execute_supabase_operation(deactivate_operation)

            if result:
                logger.info(f"✅ Policy deactivated: {policy_id}")
            return result

        except Exception as e:
            logger.error(f"❌ Policy deactivation failed: {str(e)}")
            return False

    # ==================== Statistics & Analytics ====================

    async def get_property_statistics(
        self, filters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Get property statistics (count, avg price, etc.)"""
        try:
            filters = filters or {}

            def query_stats(client: Client) -> dict:
                # Basic count query
                query = client.table("properties").select("*", count="exact")

                # Apply filters
                if filters.get("district"):
                    query = query.eq("district", filters["district"])
                if filters.get("property_type"):
                    query = query.eq("property_type", filters["property_type"])

                query = query.eq("listing_status", "active")
                response = query.execute()

                total_count = response.count or 0

                # Calculate averages (simple approach)
                properties = response.data or []
                avg_price = (
                    sum(p.get("price", 0) for p in properties if p.get("price"))
                    / len(properties)
                    if properties
                    else 0
                )
                avg_area = (
                    sum(
                        p.get("area_exclusive", 0)
                        for p in properties
                        if p.get("area_exclusive")
                    )
                    / len(properties)
                    if properties
                    else 0
                )

                return {
                    "total_count": total_count,
                    "average_price": round(avg_price),
                    "average_area": round(avg_area, 2),
                }

            stats = await execute_supabase_operation(query_stats)
            logger.info(f"✅ Property statistics calculated: {stats}")
            return stats

        except Exception as e:
            logger.error(f"❌ Property statistics failed: {str(e)}")
            return {"total_count": 0, "average_price": 0, "average_area": 0}

    async def get_policy_statistics(self) -> dict[str, Any]:
        """Get policy statistics"""
        try:

            def query_stats(client: Client) -> dict:
                # Count by type
                response = (
                    client.table("government_policies")
                    .select("policy_type", count="exact")
                    .eq("is_active", True)
                    .execute()
                )

                total_count = response.count or 0

                # Count by demographic
                demographic_response = (
                    client.table("government_policies")
                    .select("target_demographic", count="exact")
                    .eq("is_active", True)
                    .execute()
                )

                return {
                    "total_active_policies": total_count,
                    "policies_data": response.data or [],
                    "demographics_data": demographic_response.data or [],
                }

            stats = await execute_supabase_operation(query_stats)
            logger.info("✅ Policy statistics calculated")
            return stats

        except Exception as e:
            logger.error(f"❌ Policy statistics failed: {str(e)}")
            return {"total_active_policies": 0, "policies_data": [], "demographics_data": []}
