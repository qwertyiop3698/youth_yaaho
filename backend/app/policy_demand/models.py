"""미충족 정책 수요 Infrastructure 테이블."""
from sqlalchemy import Column, DateTime, Index, Integer, String, Table, UniqueConstraint, func

from ..db import metadata

policy_demand_responses = Table(
    "policy_demand_responses", metadata,
    Column("response_id", String, primary_key=True),
    Column("user_id", String, nullable=False),
    Column("session_id", String, nullable=False),
    Column("trigger_reason", String, nullable=False),
    Column("need_area", String, nullable=False),
    Column("duration", String, nullable=False),
    Column("amount", String, nullable=False),
    Column("barrier", String, nullable=False),
    Column("companion_support", String),
    Column("employment_status", String),
    Column("district_code", String),
    Column("other_text", String),
    Column("form_version", String, nullable=False),
    Column("submitted_at", DateTime, nullable=False, server_default=func.now()),
)
Index("idx_policy_demand_user_situation", policy_demand_responses.c.user_id, policy_demand_responses.c.need_area, policy_demand_responses.c.trigger_reason)
Index("idx_policy_demand_submitted", policy_demand_responses.c.submitted_at)

demand_reward_grants = Table(
    "demand_reward_grants", metadata,
    Column("reward_id", String, primary_key=True),
    Column("response_id", String, nullable=False),
    Column("user_id", String, nullable=False),
    Column("amount", Integer, nullable=False),
    Column("status", String, nullable=False),
    Column("provider_reference", String),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("updated_at", DateTime, nullable=False, server_default=func.now()),
    UniqueConstraint("response_id", name="uq_demand_reward_response"),
)

