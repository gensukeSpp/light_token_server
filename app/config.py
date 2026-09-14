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
ENV = os.getenv("ENV", "development")
# 開発用デフォルトを1回だけ設定し、本番では env 未設定時にのみ厳格に失敗させる。
# 分岐による重複代入を排除し、いかなる環境でも SECRET_KEY が None にならないようにする。
SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-secret-change-me")
if ENV == "production" and not os.getenv("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY must be set in production")
# 本番環境ならこっち、削除しないでね
# APP_URL = os.getenv("CALENDAR_TIMELINE", "https://time-table-to-line.ktde-z3837.workers.dev")
# ローカルならこっち、削除しないでね
APP_URL = os.getenv("CALENDAR_TIMELINE", "http://localhost:5173")

# アクセストークン/リフレッシュトークンの有効期限(限定組織向けに長め。env で調整可)
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

# マイルストーン close 猶予(グレース)期間(日)。waiting 遷移後、この日数を経過して closed 確定。
MILESTONE_CLOSE_GRACE_DAYS = int(os.getenv("MILESTONE_CLOSE_GRACE_DAYS", "5"))
# 猶予チェックのバックグラウンド実行間隔(分)。dev で短くする用途。
MILESTONE_CLOSE_INTERVAL_MINUTES = int(os.getenv("MILESTONE_CLOSE_INTERVAL_MINUTES", "60"))
# False のときスケジューラを自動起動しない(dev / テスト用)。default True(production 想定)
ENABLE_MILESTONE_SCHEDULER = os.getenv("ENABLE_MILESTONE_SCHEDULER", "true").lower() == "true"
