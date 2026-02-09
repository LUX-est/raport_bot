from __future__ import annotations

from dataclasses import dataclass
import os
from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class GoogleSheetsConfig:
    service_account_file: str
    spreadsheet_id: str
    sheet_reports: str
    sheet_problems: str
    sheet_edits: str
    sheet_statuses: str


@dataclass(frozen=True, slots=True)
class Config:
    bot_token: str
    database_url: str
    admin_ids: set[int]
    google_sheets: GoogleSheetsConfig | None


def load_config() -> Config:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is missing in environment (.env).")

    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot.db").strip()

    raw_admins = os.getenv("ADMIN_IDS", "").strip()
    admin_ids: set[int] = set()
    if raw_admins:
        for part in raw_admins.split(","):
            part = part.strip()
            if part:
                try:
                    admin_ids.add(int(part))
                except ValueError:
                    raise RuntimeError(f"Invalid ADMIN_IDS value: {part!r} (must be integers).")

    sa_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    ss_id = os.getenv("GOOGLE_SPREADSHEET_ID", "").strip()
    google_sheets: GoogleSheetsConfig | None = None
    if sa_file and ss_id:
        google_sheets = GoogleSheetsConfig(
            service_account_file=sa_file,
            spreadsheet_id=ss_id,
            sheet_reports=os.getenv("GOOGLE_SHEET_REPORTS", "Reports").strip() or "Reports",
            sheet_problems=os.getenv("GOOGLE_SHEET_PROBLEMS", "Problems").strip() or "Problems",
            sheet_edits=os.getenv("GOOGLE_SHEET_EDITS", "ReportEdits").strip() or "ReportEdits",
            sheet_statuses=os.getenv("GOOGLE_SHEET_STATUSES", "ReportStatuses").strip() or "ReportStatuses",
        )

    return Config(
        bot_token=bot_token,
        database_url=database_url,
        admin_ids=admin_ids,
        google_sheets=google_sheets,
    )
