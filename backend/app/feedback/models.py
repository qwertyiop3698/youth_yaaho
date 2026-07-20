"""정책 피드백 Infrastructure 계층의 SQLAlchemy Core 테이블."""
from __future__ import annotations

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Table, UniqueConstraint, func

from ..db import metadata


policy_usages = Table(
    "policy_usages", metadata,
    Column("usage_id", String, primary_key=True),
    Column("user_id", String, ForeignKey("users.user_id"), nullable=False),
    Column("policy_id", String, nullable=False),
    Column("policy_name", String, nullable=False),
    Column("policy_source", String, nullable=False),
    Column("current_status", String, nullable=False),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
    Column("updated_at", DateTime, server_default=func.now(), nullable=False),
    UniqueConstraint("user_id", "policy_id", name="uq_policy_usage_user_policy"),
)
Index("idx_policy_usages_user", policy_usages.c.user_id)
Index("idx_policy_usages_policy", policy_usages.c.policy_id)

policy_usage_status_history = Table(
    "policy_usage_status_history", metadata,
    Column("history_id", Integer, primary_key=True, autoincrement=True),
    Column("usage_id", String, ForeignKey("policy_usages.usage_id"), nullable=False),
    Column("status", String, nullable=False),
    Column("changed_at", DateTime, server_default=func.now(), nullable=False),
)
Index("idx_usage_status_history_usage", policy_usage_status_history.c.usage_id)

feedback_questions = Table(
    "feedback_questions", metadata,
    Column("question_id", String, primary_key=True),
    Column("form_version", String, nullable=False),
    Column("question_code", String, nullable=False),
    Column("prompt", String, nullable=False),
    Column("options", JSON, nullable=False),
    Column("stages", JSON, nullable=False),
    Column("position", Integer, nullable=False),
    Column("allows_other", Boolean, nullable=False, default=False),
    Column("active", Boolean, nullable=False, default=True),
    UniqueConstraint("form_version", "question_code", name="uq_feedback_question_version_code"),
)

policy_feedback = Table(
    "policy_feedback", metadata,
    Column("feedback_id", String, primary_key=True),
    Column("usage_id", String, ForeignKey("policy_usages.usage_id"), nullable=False),
    Column("user_id", String, ForeignKey("users.user_id"), nullable=False),
    Column("policy_id", String, nullable=False),
    Column("stage", String, nullable=False),
    Column("form_version", String, nullable=False),
    Column("submitted_at", DateTime, server_default=func.now(), nullable=False),
    UniqueConstraint("usage_id", "stage", name="uq_policy_feedback_usage_stage"),
)
Index("idx_policy_feedback_policy", policy_feedback.c.policy_id)

feedback_answers = Table(
    "feedback_answers", metadata,
    Column("answer_id", Integer, primary_key=True, autoincrement=True),
    Column("feedback_id", String, ForeignKey("policy_feedback.feedback_id"), nullable=False),
    Column("question_code", String, nullable=False),
    Column("choice", String, nullable=False),
    Column("other_text", String),
    UniqueConstraint("feedback_id", "question_code", name="uq_feedback_answer_question"),
)
Index("idx_feedback_answers_feedback", feedback_answers.c.feedback_id)

reward_grants = Table(
    "reward_grants", metadata,
    Column("reward_id", String, primary_key=True),
    Column("feedback_id", String, ForeignKey("policy_feedback.feedback_id"), nullable=False, unique=True),
    Column("usage_id", String, ForeignKey("policy_usages.usage_id"), nullable=False),
    Column("user_id", String, ForeignKey("users.user_id"), nullable=False),
    Column("policy_id", String, nullable=False),
    Column("stage", String, nullable=False),
    Column("amount", Integer, nullable=False),
    Column("status", String, nullable=False),
    Column("provider_reference", String),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
    Column("updated_at", DateTime, server_default=func.now(), nullable=False),
    UniqueConstraint("usage_id", "stage", name="uq_reward_grant_usage_stage"),
)
Index("idx_reward_grants_user", reward_grants.c.user_id)
