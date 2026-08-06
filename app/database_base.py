import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()
basedir = os.path.abspath(os.path.dirname(__file__))

DB_URL = (
    "mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}?charset=utf8mb4".format(
        **{
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "host": os.getenv("DB_HOST"),
            "port": os.getenv("DB_PORT"),
            "db_name": os.getenv("DB_NAME"),
        }
    )
)

engine = create_engine(DB_URL, echo=False)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = Session()

Base = declarative_base()
