from deployment.api.db.session import engine
from deployment.api.db.base import Base


def init_db():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()