"""
Appointment calendar — Month / Week / Day views of the registry records,
placed by their Appointment Date and ordered by Appointment Time.
"""

import calendar
import html
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from utils.date_utils import parse_appt_date_series

VIEWS        = ["Month", "Week", "Day"]
WEEKDAYS     = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MAX_PER_CELL = 3   # appointments shown inside a month cell before "+N more"

STATUS_ICON = {
    "pending":     "🟡",
    "in progress": "🔵",
    "completed":   "🟢",
    "rejected":    "🔴",
}

_NO_TIME = 24 * 60  # sort key for rows without a usable time — they go last


# =====================================================
# HELPERS
# =====================================================
def _time_minutes(v) -> int:
    """Minutes since midnight for "10:30", "10:30:00" or a Sheets day-fraction; _NO_TIME if unparseable."""
    s = str(v).strip()
    if not s or s in ("None", "nan"):
        return _NO_TIME
    try:
        if ":" in s:
            p = s.split(":")
            return int(float(p[0])) * 60 + int(float(p[1]))
        frac = float(s)
        if 0.0 <= frac <= 1.0:
            return round(frac * 1440)
    except (ValueError, IndexError):
        pass
    return _NO_TIME


def _fmt_minutes(m: int) -> str:
    if m >= _NO_TIME:
        return "—"
    h, mm = divmod(m, 60)
    return f"{(h % 12) or 12:02d}:{mm:02d} {'AM' if h < 12 else 'PM'}"


def _status_icon(status) -> str:
    return STATUS_ICON.get(str(status).strip().lower(), "⚪")


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Add parsed date/time helper columns and drop rows without a valid Appointment Date."""
    out = df.copy()
    out["_appt_date"] = parse_appt_date_series(out["Appointment Date"]).dt.date
    out["_mins"]      = out["Appointment Time"].map(_time_minutes) if "Appointment Time" in out else _NO_TIME
    out = out[out["_appt_date"].notna()]
    return out.sort_values(["_appt_date", "_mins"])


def _shift(anchor: date, view: str, step: int) -> date:
    if view == "Day":
        return anchor + timedelta(days=step)
    if view == "Week":
        return anchor + timedelta(weeks=step)
    # Month — move to the 1st of the previous/next month
    y, m = divmod(anchor.year * 12 + (anchor.month - 1) + step, 12)
    return date(y, m + 1, 1)


def _entry_html(row, compact: bool) -> str:
    """One appointment line. Compact = month cell (single ellipsised line)."""
    icon  = _status_icon(row.get("Title_Status", ""))
    time_ = _fmt_minutes(row["_mins"])
    party = html.escape(str(row.get("Party_Name 1", "") or "").strip() or "—")
    if compact:
        return (
            f'<div style="font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" '
            f'title="{party}">{icon} {time_} · {party}</div>'
        )
    doc = html.escape(str(row.get("Doc_Type", "") or ""))
    sro = html.escape(str(row.get("SRO", "") or ""))
    extra = " · ".join(x for x in (doc, sro) if x)
    return (
        f'<div style="font-size:12px;border-left:3px solid #c2dbf7;padding:2px 0 2px 6px;margin:4px 0">'
        f'<b>{icon} {time_}</b><br>{party}'
        + (f'<br><span style="color:#888">{extra}</span>' if extra else "")
        + "</div>"
    )


# =====================================================
# STATE CALLBACKS — run before the rerun so one click is enough
# =====================================================
def _go(step: int):
    st.session_state.cal_anchor = _shift(st.session_state.cal_anchor, st.session_state.cal_view, step)


def _go_today():
    st.session_state.cal_anchor = date.today()


def _open_day(d: date):
    st.session_state.cal_anchor = d
    st.session_state.cal_view   = "Day"


# =====================================================
# VIEWS
# =====================================================
def _render_month(appts: pd.DataFrame, anchor: date, today: date):
    by_day = {d: g for d, g in appts.groupby("_appt_date")}

    for col, name in zip(st.columns(7), WEEKDAYS):
        col.markdown(f"**{name}**")

    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(anchor.year, anchor.month):
        for col, d in zip(st.columns(7), week):
            if d.month != anchor.month:
                continue
            day_df = by_day.get(d)
            count  = 0 if day_df is None else len(day_df)
            with col.container(border=True):
                label = f"{d.day}" + (f"  ·  {count} appt" if count else "")
                st.button(label, key=f"cal_m_{d.isoformat()}", on_click=_open_day, args=(d,),
                          type="primary" if d == today else "secondary",
                          use_container_width=True)
                if count:
                    lines = [_entry_html(r, compact=True) for _, r in day_df.head(MAX_PER_CELL).iterrows()]
                    if count > MAX_PER_CELL:
                        lines.append(f'<div style="font-size:12px;color:#1565C0">+{count - MAX_PER_CELL} more</div>')
                    st.markdown("".join(lines), unsafe_allow_html=True)


def _render_week(appts: pd.DataFrame, anchor: date, today: date):
    start = anchor - timedelta(days=anchor.weekday())
    for i, col in enumerate(st.columns(7)):
        d = start + timedelta(days=i)
        day_df = appts[appts["_appt_date"] == d]
        with col.container(border=True):
            st.button(f"{WEEKDAYS[i]} {d.day:02d}", key=f"cal_w_{d.isoformat()}",
                      on_click=_open_day, args=(d,),
                      type="primary" if d == today else "secondary",
                      use_container_width=True)
            if day_df.empty:
                st.caption("No appointments")
            else:
                st.markdown("".join(_entry_html(r, compact=False) for _, r in day_df.iterrows()),
                            unsafe_allow_html=True)


def _render_day(appts: pd.DataFrame, anchor: date, display_fn):
    day_df = appts[appts["_appt_date"] == anchor]
    if day_df.empty:
        st.info(f"No appointments on {anchor.strftime('%d/%m/%Y')}.")
        return

    table = day_df.drop(columns=["_appt_date", "_mins"])
    if "Appointment Time" in table:
        table["Appointment Time"] = day_df["_mins"].map(_fmt_minutes)
    st.dataframe(display_fn(table) if display_fn else table,
                 use_container_width=True, hide_index=True)
    st.download_button("⬇️ Download CSV", table.to_csv(index=False),
                       file_name=f"appointments_{anchor.isoformat()}.csv", mime="text/csv")


# =====================================================
# ENTRY POINT
# =====================================================
def render_calendar(df: pd.DataFrame, username: str = "", display_fn=None):
    """Render the appointment calendar page body for the given records DataFrame."""
    st.session_state.setdefault("cal_anchor", date.today())
    st.session_state.setdefault("cal_view", "Month")
    today = date.today()

    # --- Controls row ---
    c_prev, c_today, c_next, c_title, c_view = st.columns([1, 1.3, 1, 6, 2.2], vertical_alignment="center")
    c_prev.button("◀", key="cal_prev", on_click=_go, args=(-1,), use_container_width=True)
    c_today.button("Today", key="cal_today", on_click=_go_today, use_container_width=True)
    c_next.button("▶", key="cal_next", on_click=_go, args=(1,), use_container_width=True)
    c_view.selectbox("View", VIEWS, key="cal_view", label_visibility="collapsed")

    view   = st.session_state.cal_view
    anchor = st.session_state.cal_anchor

    scope = st.radio("Show", ["All Records", "My Records"], horizontal=True,
                     key="cal_scope", label_visibility="collapsed")
    src = df if scope == "All Records" or not username else df[df["Created_By"] == username]
    appts = _prepare(src)

    # --- Visible range + title ---
    if view == "Month":
        first = anchor.replace(day=1)
        last  = first.replace(day=calendar.monthrange(first.year, first.month)[1])
        title = anchor.strftime("%B %Y")
    elif view == "Week":
        first = anchor - timedelta(days=anchor.weekday())
        last  = first + timedelta(days=6)
        title = f"{first.strftime('%d %b')} – {last.strftime('%d %b %Y')}"
    else:
        first = last = anchor
        title = anchor.strftime("%A, %d %B %Y")

    in_range = appts[(appts["_appt_date"] >= first) & (appts["_appt_date"] <= last)]
    c_title.markdown(f"### {title} · {len(in_range)} appointment(s)")
    st.caption("🟡 Pending · 🔵 In Progress · 🟢 Completed · 🔴 Rejected — click a day to see its full appointments.")
    st.divider()

    if view == "Month":
        _render_month(in_range, anchor, today)
    elif view == "Week":
        _render_week(in_range, anchor, today)
    else:
        _render_day(in_range, anchor, display_fn)
