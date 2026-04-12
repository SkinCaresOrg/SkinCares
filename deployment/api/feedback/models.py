from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from deployment.api.db.base import Base


class SwipeEvent(Base):
    __tablename__ = "swipe_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    product_id = Column(Integer, nullable=False, index=True)
    has_tried = Column(Boolean, nullable=False)
    reaction = Column(String, nullable=True)
    skipped_questionnaire = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class QuestionnaireResponse(Base):
    __tablename__ = "questionnaire_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    swipe_event_id = Column(
        Integer, ForeignKey("swipe_events.id"), nullable=False, index=True
    )
    user_id = Column(String, nullable=False, index=True)
    product_id = Column(Integer, nullable=False, index=True)
    reaction = Column(String, nullable=False)
    reason_tags = Column(Text, nullable=False, default="[]")
    free_text = Column(Text, nullable=False, default="")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
