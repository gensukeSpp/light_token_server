from datetime import date

from pydantic import BaseModel


class LoginForm(BaseModel):
    STAFFID: int
    PASSWORD: str
    remember_me: bool = False


class EventCreate(BaseModel):
    staff_id: int
    group: int
    start_time: str
    end_time: str
    title: str
    summary: str | None = None
    progress: str | None = None
    milestone_id: int | None = None
    completed: bool = False


class EventUpdate(BaseModel):
    summary: str | None = None
    progress: str | None = None
    milestone_id: int | None = None
    completed: bool | None = None


class EventDateItem(BaseModel):
    """移動/リサイズ後のイベントの日時。start_time / end_time は ISO 形式文字列。"""

    id: int
    start_time: str
    end_time: str


class EventDateUpdate(BaseModel):
    """POST /date/update 用。Timeline/Calendar のドラッグ&ドロップ保存時に送られる。"""

    data: list[EventDateItem]


class MilestoneCreate(BaseModel):
    """POST /milestone/add 用。staff_id / status / created_at / color はサーバー側で設定。
    色は open 中のマイルストーンと被らないよう自動選択する。
    """

    title: str
    description: str | None = None
    guideline_end_date: date | None = None


class MilestoneUpdate(BaseModel):
    """POST /milestone/update/{id} 用。accomplished_date 入力で close する。
    status は open → closed へ遷移する(String)。waiting は再 open の猶予期間用。
    """

    accomplished_date: date