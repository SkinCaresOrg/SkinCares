import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()
app_env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
is_production = (
    app_env in {"prod", "production"}
    or os.getenv("VERCEL_ENV") == "production"
    or os.getenv("RENDER") == "true"
)

SECRET_KEY = os.getenv("SECRET_KEY")
DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("POSTGRES_URL")
    or os.getenv("POSTGRES_PRISMA_URL")
    or os.getenv("POSTGRES_URL_NON_POOLING")
)

if not SECRET_KEY and not is_production:
    SECRET_KEY = "dev-local-secret"

if not DATABASE_URL:
    if is_production:
        raise ValueError(
            "Database URL is not set. Define DATABASE_URL or one of: "
            "POSTGRES_URL, POSTGRES_PRISMA_URL, POSTGRES_URL_NON_POOLING"
        )
    DATABASE_URL = "sqlite:///./local.db"

if (
    DATABASE_URL.startswith("postgresql://")
    and "+" not in DATABASE_URL.split("://", 1)[0]
):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
