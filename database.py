from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "mysql+pymysql://avnadmin:AVNS_quj7rIjnriupzY-GcK8@mysql-sih-2-mhaskesagar2823-8ec0.c.aivencloud.com:11920/jjm_water_monitoring"

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "ssl": {}
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
