import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from datetime import date

from app.database_base import Base, get_db
from app.main import app
from app.models import StaffLogin, User, Team, EventORM


@pytest.fixture
def db_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = factory()
    user = User(1001)
    user.DISPLAY = True
    user.TEAM_CODE = 3
    db.add(user)
    db.add(StaffLogin(1001, "secret", True))
    team = Team(3)
    team.NAME = "Team A"
    team.SHORTNAME = "SHORT_A"
    db.add(team)
    db.add(
        EventORM(
            staff_id=1001,
            group_id=3,
            start_time=date(2026, 8, 1),
            end_time=date(2026, 8, 1),
            title="t",
            summary=None,
            progress="p",
        )
    )
    db.commit()
    db.close()
    return factory


@pytest.fixture
def client(db_session_factory):
    def override_get_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
