import os

from dotenv import load_dotenv

load_dotenv()


def _db_url() -> str:
    return (
        "postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}".format(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            db_name=os.getenv("DB_NAME"),
        )
    )


DB_URL = os.getenv("DATABASE_URL", _db_url())
SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-secret-change-me")
ENV = os.getenv("ENV", "development")