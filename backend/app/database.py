from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import get_settings

s = get_settings()
url = URL.create("mysql+pymysql", username=s.DB_USER, password=s.DB_PASSWORD,
                 host=s.DB_HOST, port=s.DB_PORT, database=s.DB_NAME)
engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as db:
        yield db
