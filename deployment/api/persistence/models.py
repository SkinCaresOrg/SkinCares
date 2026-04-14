from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.sql import func
from sqlalchemy.types import JSON, LargeBinary

from deployment.api.db.base import Base

AutoPKType = BigInteger().with_variant(Integer, "sqlite")
TextArrayType = ARRAY(Text).with_variant(JSON, "sqlite")
UUIDType = UUID(as_uuid=False).with_variant(String(36), "sqlite")


class UserProfileState(Base):
    __tablename__ = "user_profiles"

    user_id = Column(String, primary_key=True, index=True)
    profile = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )


class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, index=True)
    product_name = Column(Text, nullable=False)
    brand = Column(Text, nullable=True)
    category = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=True)
    image_url = Column(Text, nullable=True)
    ingredients = Column(TextArrayType, nullable=True)
    short_description = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProductDupe(Base):
    __tablename__ = "product_dupes"

    id = Column(AutoPKType, primary_key=True, autoincrement=True, index=True)
    source_product_id = Column(
        Integer,
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dupe_product_id = Column(
        Integer,
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
    )
    dupe_score = Column(Float, nullable=False)
    cosine_sim = Column(Float, nullable=False)
    price_score = Column(Float, nullable=False)
    ingredient_group_score = Column(Float, nullable=False)
    explanation = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "source_product_id",
            "dupe_product_id",
            name="uq_product_dupes_source_dupe",
        ),
    )


class UserProductEvent(Base):
    __tablename__ = "user_product_events"

    id = Column(AutoPKType, primary_key=True, autoincrement=True, index=True)
    user_id = Column(UUIDType, index=True, nullable=False)
    product_id = Column(Integer, nullable=False)
    event_type = Column(Text, nullable=False)
    reaction = Column(Text, nullable=True)
    reason_tags = Column(JSON, nullable=False, default=list)
    free_text = Column(Text, nullable=True)
    has_tried = Column(Boolean, nullable=False)
    skipped_questionnaire = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserFeedbackEvent(Base):
    __tablename__ = "user_feedback_events"

    id = Column(AutoPKType, primary_key=True, autoincrement=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    product_id = Column(Integer, nullable=False)
    has_tried = Column(Boolean, nullable=False)
    reaction = Column(Text, nullable=True)
    reason_tags = Column(JSON, nullable=False, default=list)
    free_text = Column(Text, nullable=False, default="")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserModelState(Base):
    __tablename__ = "user_model_state"

    user_id = Column(UUIDType, primary_key=True, index=True)
    interactions = Column(Integer, nullable=False, default=0)
    liked_count = Column(Integer, nullable=False, default=0)
    disliked_count = Column(Integer, nullable=False, default=0)
    irritation_count = Column(Integer, nullable=False, default=0)
    liked_reasons = Column(JSON, nullable=False, default=list)
    disliked_reasons = Column(JSON, nullable=False, default=list)
    irritation_reasons = Column(JSON, nullable=False, default=list)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RecommendationLog(Base):
    __tablename__ = "recommendation_log"

    id = Column(AutoPKType, primary_key=True, autoincrement=True, index=True)
    user_id = Column(UUIDType, index=True, nullable=False)
    product_id = Column(Integer, nullable=False)
    session_id = Column(UUIDType, nullable=True)
    model_used = Column(Text, nullable=True)
    rank_position = Column(Integer, nullable=True)
    score = Column(Float, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserWishlist(Base):
    __tablename__ = "user_wishlists"

    id = Column(AutoPKType, primary_key=True, autoincrement=True, index=True)
    user_id = Column(UUIDType, nullable=False, index=True)
    product_id = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "user_id", "product_id", name="uq_user_wishlists_user_product"
        ),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(AutoPKType, primary_key=True, autoincrement=True, index=True)
    user_id = Column(UUIDType, nullable=True, index=True)
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ModelCheckpoint(Base):
    __tablename__ = "model_checkpoints"

    id = Column(AutoPKType, primary_key=True, autoincrement=True, index=True)
    user_id = Column(UUIDType, nullable=False, index=True)
    model_type = Column(Text, nullable=False)
    model_blob = Column(LargeBinary, nullable=True)
    n_updates = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
