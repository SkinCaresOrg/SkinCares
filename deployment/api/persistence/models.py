from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from deployment.api.db.base import Base


class UserProfileState(Base):
    __tablename__ = "user_profiles"

    user_id = Column(String, primary_key=True, index=True)
    profile = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class UserFeedbackEvent(Base):
    __tablename__ = "user_feedback_events"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    product_id = Column(Integer, nullable=False)
    has_tried = Column(Boolean, nullable=False)
    reaction = Column(String, nullable=True)
    reason_tags = Column(JSON, nullable=False, default=list)
    free_text = Column(Text, nullable=False, default="")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
