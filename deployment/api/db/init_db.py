from deployment.api.db.session import engine
from deployment.api.db.base import Base

# Import models so SQLAlchemy metadata includes all tables.
from deployment.api.auth import models as auth_models  # noqa: F401
from deployment.api.persistence import models as persistence_models  # noqa: F401


def init_db():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
