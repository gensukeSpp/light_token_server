from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Float,
    DateTime,
    Date,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import expression
from werkzeug.security import generate_password_hash, check_password_hash

from .database_base import Base

# SQLAlchemyのマイグレーションツール Alambic導入時のトラブルシューティングまとめ
# https://www.sria.co.jp/blog/2021/06/5545/


class User(Base):
    __tablename__ = "M_STAFFINFO"
    STAFFID = Column(Integer, primary_key=True, index=True, nullable=False)
    DEPARTMENT_CODE = Column(Integer, index=True, nullable=True)
    TEAM_CODE = Column(Integer, index=True, nullable=True)
    CONTRACT_CODE = Column(Integer, index=True, nullable=True)
    JOBTYPE_CODE = Column(Integer, index=True, nullable=True)
    POST_CODE = Column(Integer, index=True, nullable=True)
    LNAME = Column(String(50), index=True, nullable=True)
    FNAME = Column(String(50), index=True, nullable=True)
    LKANA = Column(String(50), index=True, nullable=True)
    FKANA = Column(String(50), index=True, nullable=True)
    POST = Column(String(10), index=True, nullable=True)
    ADRESS1 = Column(String(50), index=True, nullable=True)
    ADRESS2 = Column(String(50), index=True, nullable=True)
    TEL1 = Column(String(50), index=True, nullable=True)
    TEL2 = Column(String(50), index=True, nullable=True)
    BIRTHDAY = Column(DateTime, index=True, nullable=True)
    INDAY = Column(DateTime, index=True, nullable=True)
    OUTDAY = Column(DateTime, index=True, nullable=True)
    STANDDAY = Column(DateTime, index=True, nullable=True)
    SOCIAL_INSURANCE = Column(Integer, index=True, nullable=True)
    EMPLOYMENT_INSURANCE = Column(Integer, index=True, nullable=True)
    EXPERIENCE = Column(Integer, index=True, nullable=True)
    TABLET = Column(Integer, index=True, nullable=True)
    SINGLE = Column(Integer, index=True, nullable=True)
    SUPPORT = Column(Integer, index=True, nullable=True)
    HOUSE = Column(Integer, index=True, nullable=True)
    DISTANCE = Column(Float, index=True, nullable=True)
    REMARK = Column(String(100), index=True, nullable=True)
    DISPLAY = Column(Boolean, index=True, nullable=False)
    login = relationship("StaffLogin", backref="M_STAFFINFO")

    def __init__(self, STAFFID):
        self.STAFFID = STAFFID


class Team(Base):
    __tablename__ = "M_TEAM"
    CODE = Column(Integer, primary_key=True, index=True, nullable=False)
    NAME = Column(String(50), index=True, nullable=False)
    SHORTNAME = Column(String(25), index=True, nullable=False)
    event = relationship("EventORM", backref="M_TEAM")

    def __init__(self, CODE):
        self.CODE = CODE


class StaffLogin(Base):
    __tablename__ = "M_LOGININFO"
    id = Column(Integer, primary_key=True)
    STAFFID = Column(
        Integer,
        ForeignKey("M_STAFFINFO.STAFFID"),
        unique=True,
        index=True,
        nullable=False,
    )
    PASSWORD_HASH = Column(String(128), index=True, nullable=True)
    ADMIN = Column(Boolean, index=True, nullable=True)
    event = relationship("EventORM", backref="M_LOGININFO")

    def __init__(self, STAFFID, PASSWORD, ADMIN):
        self.STAFFID = STAFFID
        self.PASSWORD_HASH = generate_password_hash(PASSWORD)
        self.ADMIN = ADMIN

    def check_password(self, PASSWORD):
        return check_password_hash(self.PASSWORD_HASH, PASSWORD)


class EventORM(Base):
    __tablename__ = "T_TIMELINE_EVENT"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("M_LOGININFO.STAFFID"), nullable=False)
    group_id = Column(Integer, ForeignKey("M_TEAM.CODE"), nullable=False)
    start_time = Column(DateTime(), nullable=False)
    end_time = Column(DateTime(), nullable=False)
    title = Column(String(50), index=True, nullable=False)
    summary = Column(String(50), nullable=True)
    progress = Column(String(256), index=True, nullable=True)
    milestone_id = Column(Integer, ForeignKey("M_MILESTONE.id"), nullable=True)
    completed = Column(Boolean, server_default=expression.false(), nullable=False)

    # SQLAlchemyでクラスオブジェクトを辞書型(dictionary)に変換する方法
    # https://qiita.com/hayashi-ay/items/4da431003e8d2aff8
    def to_dict(self):
        f = "%Y-%m-%dT%H:%M:%S.000Z"
        return {
            "id": self.id,
            "staff_id": self.staff_id,
            "group": self.group_id,
            "start": datetime.strftime(self.start_time, f),
            "end": datetime.strftime(self.end_time, f),
            "title": self.title,
            "summary": self.summary,
            "progress": self.progress,
            "milestone_id": self.milestone_id,
            "completed": self.completed,
        }


# マイルストーン status (requirement-03.md 2026-08-27 変更)。
# open=作成直後, waiting=再 open の猶予期間 (waiting for close), closed=達成済み。
# デフォルトは open。
MILESTONE_OPEN = "open"
MILESTONE_WAITING = "waiting"
MILESTONE_CLOSED = "closed"


class MilestoneORM(Base):
    """マイルストーン (requirement-03.md)。
    グループ横断共有のため group_id カラムは持たない。
    status: "open" / "waiting" / "closed" の String(10)。デフォルト open。
    closed になった後も再 open の猶予期間 (waiting) を経て確定する予定。
    """

    __tablename__ = "M_MILESTONE"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(
        Integer,
        ForeignKey("M_LOGININFO.STAFFID"),
        nullable=False,
    )
    title = Column(String(100), index=True, nullable=False)
    description = Column(String(256), nullable=True)
    color = Column(String(10), nullable=False)
    status = Column(String(10), server_default=MILESTONE_OPEN, nullable=False)
    created_at = Column(Date, nullable=False)
    guideline_end_date = Column(Date, nullable=True)
    accomplished_date = Column(Date, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "staff_id": self.staff_id,
            "title": self.title,
            "description": self.description,
            "color": self.color,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at is not None else None,
            "guideline_end_date": (self.guideline_end_date.isoformat() if self.guideline_end_date is not None else None),
            "accomplished_date": (self.accomplished_date.isoformat() if self.accomplished_date is not None else None),
        }
