from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# UPDATE THIS LINE WITH YOUR MYSQL PASSWORD
DATABASE_URL = "mysql+pymysql://avnadmin:AVNS_quj7rIjnriupzY-GcK8@mysql-sih-2-mhaskesagar2823-8ec0.c.aivencloud.com:11920/jjm_water_monitoring?ssl_ca=/etc/ssl/certs/ca-certificates.crt"

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=20, max_overflow=40)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()