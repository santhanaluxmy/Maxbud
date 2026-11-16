from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import get_settings

s = get_settings()
url = URL.create("mysql+pymysql", username=s.DB_USER, password=s.DB_PASSWORD,
                 host=s.DB_HOST, port=s.DB_PORT, database=s.DB_NAME)
connect_args = {"connect_timeout": 10}
if s.DB_SSL_CA:
    connect_args.update(ssl_ca=s.DB_SSL_CA, ssl_verify_cert=True, ssl_verify_identity=True)
engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800, pool_size=5, max_overflow=10, hide_parameters=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as db:
        yield db
