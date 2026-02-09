from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@dataclass(frozen=True, slots=True)
class SheetsTarget:
    spreadsheet_id: str
    sheet_reports: str
    sheet_problems: str
    sheet_edits: str
    sheet_statuses: str


class GoogleSheetsClient:
    

    _APPROVED_STATUSES = {
        "approved", "confirm", "confirmed", "accepted", "ok",
        "подтвержден", "подтверждён", "принят", "принято", "одобрен", "одобрено",
    }

    _REJECTED_STATUSES = {
        "rejected", "declined", "denied", "cancelled", "canceled",
        "отклонен", "отклонён", "отказ", "не принято", "непринято",
    }

    def __init__(self, service_account_file: str, target: SheetsTarget):
        creds = Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
        self._service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        self._target = target
        self._sheet_titles_cache: list[str] | None = None

    def ensure_sheets_exist(self) -> None:
        
        meta = self._service.spreadsheets().get(spreadsheetId=self._target.spreadsheet_id).execute()
        existing = {s["properties"]["title"] for s in meta.get("sheets", [])}

        need = [
            self._target.sheet_reports,
            self._target.sheet_problems,
            self._target.sheet_edits,
            self._target.sheet_statuses,
        ]

        requests: list[dict[str, Any]] = []
        for title in need:
            if title and title not in existing:
                requests.append({"addSheet": {"properties": {"title": title}}})

        if requests:
            self._service.spreadsheets().batchUpdate(
                spreadsheetId=self._target.spreadsheet_id,
                body={"requests": requests},
            ).execute()

        self._sheet_titles_cache = None

    def _should_write_report_to_month_sheet(self, payload: dict[str, Any]) -> bool:
        
        status_raw = (
            payload.get("status")
            or payload.get("new_status")
            or payload.get("report_status")
            or ""
        )
        s = str(status_raw).strip().lower()

        if not s:
            return False

        if s in self._REJECTED_STATUSES:
            return False

        return s in self._APPROVED_STATUSES

    def _get_sheet_titles(self) -> list[str]:
        if self._sheet_titles_cache is None:
            meta = self._service.spreadsheets().get(spreadsheetId=self._target.spreadsheet_id).execute()
            self._sheet_titles_cache = [s["properties"]["title"] for s in meta.get("sheets", [])]
        return self._sheet_titles_cache

    def _resolve_title_ci(self, wanted: str) -> str | None:
        wanted_l = wanted.strip().lower()
        for t in self._get_sheet_titles():
            if t.strip().lower() == wanted_l:
                return t
        return None

    def _append_values(self, sheet_title: str, a1_range: str, values: list[Any]) -> None:
        self._service.spreadsheets().values().append(
            spreadsheetId=self._target.spreadsheet_id,
            range=f"{sheet_title}!{a1_range}",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [values]},
        ).execute()

    def _update_values(self, sheet_title: str, a1_range: str, values: list[Any]) -> None:
        self._service.spreadsheets().values().update(
            spreadsheetId=self._target.spreadsheet_id,
            range=f"{sheet_title}!{a1_range}",
            valueInputOption="USER_ENTERED",
            body={"values": [values]},
        ).execute()

    def _find_first_empty_row(self, sheet_title: str, col: str = "A", start_row: int = 2, max_rows: int = 5000) -> int:
       
        end_row = start_row + max_rows - 1
        rng = f"{col}{start_row}:{col}{end_row}"

        resp = self._service.spreadsheets().values().get(
            spreadsheetId=self._target.spreadsheet_id,
            range=f"{sheet_title}!{rng}",
            majorDimension="COLUMNS",
        ).execute()

        col_values = (resp.get("values") or [[]])[0]
        for idx, v in enumerate(col_values, start=start_row):
            if v is None or str(v).strip() == "":
                return idx

        return start_row + len(col_values)

    @staticmethod
    def _parse_report_date(value: Any) -> date | None:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None

        try:
            return date.fromisoformat(s)  
        except Exception:
            pass

        try:  # DD.MM.YYYY
            parts = s.split(".")
            if len(parts) == 3:
                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                return date(y, m, d)
        except Exception:
            pass

        try:  
            parts = s.split("/")
            if len(parts) == 3:
                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                return date(y, m, d)
        except Exception:
            pass

        return None

    @staticmethod
    def _parse_created_at_utc(value: Any) -> date | None:
        
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None

        s_norm = s.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s_norm)
            return dt.date()
        except Exception:
            return None
    @staticmethod
    def _month_tab_candidates(month: int) -> list[str]:
        c: list[str] = []
        c.append(f"0.{month}")
        c.append(f"0.{month:02d}")
        c.append(f"{month:02d}")
        c.append(str(month))
        if month >= 10:
            c.append(f"1.{month - 10}")
        out: list[str] = []
        seen = set()
        for x in c:
            x = str(x).strip()
            if not x:
                continue
            xl = x.lower()
            if xl in seen:
                continue
            seen.add(xl)
            out.append(x)
        return out

    def _month_sheet_for_payload(self, payload: dict[str, Any]) -> str | None:
        d = self._parse_report_date(payload.get("report_date"))
        if d is None:
            d = self._parse_created_at_utc(payload.get("created_at_utc"))
        if d is None:
            d = date.today()
        for cand in self._month_tab_candidates(d.month):
            resolved = self._resolve_title_ci(cand)
            if resolved:
                return resolved

        return None

    @staticmethod
    def _sum_qty(tasks_map: dict[str, int], keys: list[str]) -> int:
        total = 0
        for k in keys:
            kk = k.strip().lower()
            if kk in tasks_map:
                total += int(tasks_map.get(kk, 0) or 0)
        return int(total)

    def append_report(self, payload: dict[str, Any]) -> None:
        if not self._should_write_report_to_month_sheet(payload):
            logger.info(
                "Skip report write (not approved): report_id=%s status=%s",
                payload.get("report_id"),
                payload.get("status") or payload.get("new_status") or payload.get("report_status"),
            )
            return

        month_sheet = self._month_sheet_for_payload(payload)

        if month_sheet is None:
            d = (
                self._parse_report_date(payload.get("report_date"))
                or self._parse_created_at_utc(payload.get("created_at_utc"))
                or date.today()
            )
            logger.warning(
                "Month sheet not found: report_id=%s month=%s candidates=%s",
                payload.get("report_id"),
                d.month,
                self._month_tab_candidates(d.month),
            )

        tasks_list = payload.get("tasks", []) or []
        tasks_map: dict[str, int] = {}
        for t in tasks_list:
            name = str(t.get("type") or "").strip().lower()
            try:
                qty = int(t.get("quantity") or 0)
            except Exception:
                qty = 0
            if not name:
                continue
            tasks_map[name] = tasks_map.get(name, 0) + max(qty, 0)

        qty_charge = self._sum_qty(tasks_map, ["зарядка(scooter)", "зарядка", "сбор на зарядку"])
        qty_build = self._sum_qty(tasks_map, ["сбор"])
        qty_move = self._sum_qty(tasks_map, ["перестановка"])
        qty_deploy = self._sum_qty(tasks_map, ["deploy", "деплой"])
        qty_batt = self._sum_qty(tasks_map, ["замена батареи", "замена батарей"])

        known = {
            "зарядка(scooter)", "зарядка", "сбор на зарядку",
            "сбор",
            "перестановка",
            "deploy", "деплой",
            "замена батареи", "замена батарей",
        }
        extra_parts: list[str] = []
        for k, v in tasks_map.items():
            if k not in known and v:
                extra_parts.append(f"{k}={v}")

        comment = (payload.get("comment") or "").strip()
        if extra_parts:
            comment = (comment + (" | " if comment else "") + "другое: " + "; ".join(extra_parts)).strip()

        full_name = f"{payload.get('first_name') or ''} {payload.get('last_name') or ''}".strip()
        if not full_name:
            full_name = str(payload.get("tg_id") or "")

        partner_name = str(payload.get("partner_name") or "").strip()

        d = self._parse_report_date(payload.get("report_date"))
        if d is None:
            d = self._parse_created_at_utc(payload.get("created_at_utc"))
        date_cell = d.strftime("%d.%m.%Y") if d else str(payload.get("report_date") or "")

        row = [
            date_cell,      # A
            full_name,      # B
            partner_name,   # C
            qty_charge,     # D
            qty_build,      # E
            qty_move,       # F
            qty_deploy,     # G
            qty_batt,       # H
            "",             # I
            comment,        # J
        ]

        if month_sheet:
            r = self._find_first_empty_row(month_sheet, col="A", start_row=2, max_rows=5000)
            self._update_values(month_sheet, f"A{r}:J{r}", row)
            return

        self._append_values(self._target.sheet_reports, "A:Z", [
            payload.get("event", "report_created"),
            payload.get("created_at_utc"),
            payload.get("report_id"),
            payload.get("tg_id"),
            payload.get("first_name"),
            payload.get("last_name"),
            payload.get("position"),
            payload.get("city"),
            payload.get("report_date"),
            payload.get("start_time"),
            payload.get("end_time"),
            "; ".join([f"{t.get('type')}={t.get('quantity')}" for t in tasks_list]),
            payload.get("comment"),
            len(payload.get("media", []) or []),
            ",".join([m.get("file_id", "") for m in (payload.get("media", []) or [])]),
            payload.get("status"),
            payload.get("edit_count", 0),
            payload.get("edited_at_utc"),
            payload.get("edited_by_tg_id"),
        ])

    def append_problem(self, payload: dict[str, Any]) -> None:
        media_ids = ",".join([m.get("file_id", "") for m in (payload.get("media", []) or [])])
        self._append_values(self._target.sheet_problems, "A:Z", [
            payload.get("event", "problem_created"),
            payload.get("created_at_utc"),
            payload.get("problem_id"),
            payload.get("tg_id"),
            payload.get("first_name"),
            payload.get("last_name"),
            payload.get("position"),
            payload.get("city"),
            payload.get("problem_type"),
            payload.get("description"),
            payload.get("address"),
            payload.get("scooter_number"),
            payload.get("urgency"),
            len(payload.get("media", []) or []),
            media_ids,
        ])

    def append_report_edit(self, payload: dict[str, Any]) -> None:
        self._append_values(self._target.sheet_edits, "A:Z", [
            payload.get("event", "report_edited"),
            payload.get("edited_at_utc"),
            payload.get("report_id"),
            payload.get("editor_tg_id"),
            payload.get("editor_name"),
            payload.get("edit_count"),
        ])

    def append_report_status(self, payload: dict[str, Any]) -> None:
        self._append_values(self._target.sheet_statuses, "A:Z", [
            payload.get("event", "report_status"),
            payload.get("changed_at_utc"),
            payload.get("report_id"),
            payload.get("status"),
            payload.get("admin_tg_id"),
            payload.get("admin_comment"),
        ])
