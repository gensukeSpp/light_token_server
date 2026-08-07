import os

from dotenv import load_dotenv

load_dotenv()


def _db_url() -> str:
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME")

    missing = [
        name
        for name, value in (
            ("DB_USER", user),
            ("DB_PASSWORD", password),
            ("DB_NAME", db_name),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("Missing required database environment variables: " + ", ".join(missing))

    return "postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}".format(
        user=user,
        password=password,
        host=host,
        port=port,
        db_name=db_name,
    )


DB_URL = os.getenv("DATABASE_URL") or _db_url()
SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-secret-change-me")
ENV = os.getenv("ENV", "development")
SECRET_KEY = os.getenv("SECRET_KEY")
if ENV == "production" and not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set in production")
APP_URL = os.getenv("CLOUD_TIMETABLE4", "http://localhost:5173")
