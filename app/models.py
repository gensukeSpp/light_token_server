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
    __tablename__ = "M_LOGGININFO"
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
    event = relationship("EventORM", backref="M_LOGGININFO")

    def __init__(self, STAFFID, PASSWORD, ADMIN):
        self.STAFFID = STAFFID
        self.PASSWORD_HASH = generate_password_hash(PASSWORD)
        self.ADMIN = ADMIN

    def check_password(self, PASSWORD):
        return check_password_hash(self.PASSWORD_HASH, PASSWORD)


class EventORM(Base):
    __tablename__ = "T_TIMELINE_EVENT"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("M_LOGGININFO.STAFFID"), nullable=False)
    group_id = Column(Integer, ForeignKey("M_TEAM.CODE"), nullable=False)
    start_time = Column(DateTime(), nullable=False)
    end_time = Column(DateTime(), nullable=False)
    title = Column(String(50), index=True, nullable=False)
    summary = Column(String(50), nullable=True)
    progress = Column(String(255), index=True, nullable=True)

    # SQLAlchemyでクラスオブジェクトを辞書型(dictionary)に変換する方法
    # https://qiita.com/hayashi-ay/items/4dc431003e7866d2aff8
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
        }
