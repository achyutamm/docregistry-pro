"""
Appointment calendar — Teams / Google-Calendar style Month, Week and Day views
of the registry records (FullCalendar via streamlit-calendar), placed by
Appointment Date and Appointment Time.
"""

import calendar as pycal
import html
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import streamlit as st
from streamlit_calendar import calendar as fullcalendar

from utils.date_utils import office_hours_minutes, parse_appt_date_series

VIEWS = ["Month", "Week", "Day"]
FC_VIEW = {"Month": "dayGridMonth", "Week": "timeGridWeek", "Day": "timeGridDay"}

IST = timezone(timedelta(hours=5, minutes=30))
APPT_MINUTES = 30   # block length drawn for each appointment in Week / Day
CAL_HEIGHT   = 760  # px — fixed calendar height (see the iframe min-height note in render_calendar)
_NO_TIME = 24 * 60  # sort key for rows without a usable time — shown in the "No time" row

# Teams-like pastel chip per Title_Status: (background, accent border, text)
STATUS_STYLE = {
    "pending":     ("#FFF4CE", "#E0A800", "#5C4400"),
    "in progress": ("#DEECF9", "#2F6FDB", "#0B3A75"),
    "completed":   ("#DFF6DD", "#2E9E4F", "#0E4B22"),
    "rejected":    ("#FDE7E9", "#D13438", "#7A1015"),
}
DEFAULT_STYLE = ("#E8E8F7", "#6264A7", "#2B2D6E")
STATUS_ICON = {"pending": "🟡", "in progress": "🔵", "completed": "🟢", "rejected": "🔴"}

CUSTOM_CSS = """
.fc { font-family: "Source Sans Pro", "Segoe UI", sans-serif; font-size: 13px; }
.fc-theme-standard td, .fc-theme-standard th, .fc-theme-standard .fc-scrollgrid { border-color: #E6E6EE; }
.fc .fc-col-header-cell { background: #FAFAFC; }
.fc .fc-col-header-cell-cushion { color: #555; font-weight: 600; padding: 8px 4px; text-decoration: none; }
.fc .fc-daygrid-day-number { color: #333; font-size: 14px; padding: 6px 8px; text-decoration: none; }
.fc .fc-day-today { background: #F4F4FC !important; }
.fc .fc-daygrid-day.fc-day-today .fc-daygrid-day-number {
    background: #6264A7; color: #fff; border-radius: 50%; width: 26px; height: 26px;
    display: flex; align-items: center; justify-content: center; margin: 4px; padding: 0;
}
.fc .fc-col-header-cell.fc-day-today .fc-col-header-cell-cushion { color: #6264A7; }
.fc .fc-daygrid-day { cursor: pointer; }
.fc .fc-daygrid-day:hover { background: #F7F7FB; }
.fc .fc-event {
    border-width: 0 0 0 4px; border-radius: 4px; padding: 1px 5px; margin: 1px 3px;
    cursor: pointer; box-shadow: 0 1px 1px rgba(0,0,0,.04);
}
.fc .fc-event:hover { filter: brightness(0.96); }
.fc .fc-daygrid-event { white-space: nowrap; overflow: hidden; }
.fc .fc-event-time { font-weight: 600; }
.fc .fc-event-title { font-weight: 500; }
.fc .fc-more-link { color: #6264A7; font-weight: 600; }
.fc .fc-timegrid-slot { height: 3em; }
.fc .fc-timegrid-event .fc-event-main { padding: 2px 2px; line-height: 1.25; }
.fc .fc-timegrid-slot-label-cushion, .fc .fc-timegrid-axis-cushion { color: #777; font-size: 12px; }
.fc .fc-timegrid-now-indicator-line { border-color: #6264A7; border-width: 2px 0 0; }
.fc .fc-timegrid-now-indicator-arrow { border-color: #6264A7; }
"""


# =====================================================
# HELPERS
# =====================================================
def _now() -> datetime:
    """Office wall-clock time (IST), independent of the server's timezone."""
    return datetime.now(IST).replace(tzinfo=None)


def _time_minutes(v) -> int:
    """Minutes since midnight for "10:30", "10:30:00" or a Sheets day-fraction; _NO_TIME if unparseable."""
    s = str(v).strip()
    if not s or s in ("None", "nan"):
        return _NO_TIME
    try:
        if ":" in s:
            p = s.split(":")
            return office_hours_minutes(int(float(p[0])) * 60 + int(float(p[1])))
        frac = float(s)
        if 0.0 <= frac <= 1.0:
            return office_hours_minutes(round(frac * 1440))
    except (ValueError, IndexError):
        pass
    return _NO_TIME


def _fmt_minutes(m: int) -> str:
    if m >= _NO_TIME:
        return "—"
    h, mm = divmod(m, 60)
    return f"{(h % 12) or 12:02d}:{mm:02d} {'AM' if h < 12 else 'PM'}"


def _cell(row, col) -> str:
    v = row.get(col, "")
    return "" if pd.isna(v) else str(v).strip()


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


def _to_events(appts: pd.DataFrame, view: str) -> list:
    events = []
    for idx, row in appts.iterrows():
        status = _cell(row, "Title_Status")
        bg, border, text = STATUS_STYLE.get(status.lower(), DEFAULT_STYLE)
        party = _cell(row, "Party_Name 1") or "—"
        doc   = _cell(row, "Doc_Type")
        title = f"{party} · {doc}" if doc else party
        if view == "Day" and _cell(row, "SRO"):
            title += f" · {_cell(row, 'SRO')}"

        ev = {
            "id": str(idx), "title": title,
            "backgroundColor": bg, "borderColor": border, "textColor": text,
        }
        d = row["_appt_date"]
        if row["_mins"] >= _NO_TIME:
            ev.update(start=d.isoformat(), allDay=True)
        else:
            start = datetime.combine(d, datetime.min.time()) + timedelta(minutes=int(row["_mins"]))
            ev.update(start=start.isoformat(),
                      end=(start + timedelta(minutes=APPT_MINUTES)).isoformat())
        events.append(ev)
    return events


def _slot_range(appts: pd.DataFrame) -> tuple:
    """Working-hours window for Week/Day, stretched to fit any early/late appointment."""
    timed = appts.loc[appts["_mins"] < _NO_TIME, "_mins"]
    lo, hi = 8, 20
    if not timed.empty:
        lo = min(lo, int(timed.min()) // 60)
        hi = max(hi, min(24, (int(timed.max()) + APPT_MINUTES) // 60 + 1))
    return f"{lo:02d}:00:00", f"{hi:02d}:00:00"


# =====================================================
# STATE CALLBACKS — run before the rerun so one click is enough
# =====================================================
def _reset_clicks():
    """Forget the open detail panel and the last handled click when the view or date changes."""
    st.session_state.pop("cal_selected", None)
    st.session_state.pop("cal_last_click", None)


def _go(step: int):
    _reset_clicks()
    st.session_state.cal_anchor = _shift(st.session_state.cal_anchor, st.session_state.cal_view, step)


def _go_today():
    _reset_clicks()
    st.session_state.cal_anchor = _now().date()


def _open_day(d: date):
    _reset_clicks()
    st.session_state.cal_anchor = d
    st.session_state.cal_view   = "Day"


# =====================================================
# DETAIL PANELS
# =====================================================
def _render_details(row, display_fn=None):
    """Every column of the record, in sheet order, labelled with the app's display names."""
    status = _cell(row, "Title_Status")
    _, border, _ = STATUS_STYLE.get(status.lower(), DEFAULT_STYLE)
    cols   = [c for c in row.index if not str(c).startswith("_")]
    labels = (dict(zip(cols, display_fn(pd.DataFrame(columns=cols)).columns))
              if display_fn else {c: c for c in cols})
    fields, wide = [], []   # wide = free-text fields (Remark) shown full-width at the bottom
    for c in cols:
        if c == "Appointment Date":
            value = row["_appt_date"].strftime("%a, %d %b %Y")
        elif c == "Appointment Time":
            value = _fmt_minutes(row["_mins"])
        else:
            value = _cell(row, c)
        value = html.escape(value).replace("\n", "<br>")
        (wide if c == "Remark" else fields).append((labels.get(c, c), value))
    with st.container(border=True):
        head, close = st.columns([6, 1], vertical_alignment="center")
        head.markdown(
            f"#### {html.escape(_cell(row, 'Party_Name 1')) or '—'} "
            f"<span style='font-size:13px;background:{border};color:#fff;border-radius:10px;"
            f"padding:2px 10px;vertical-align:middle'>{status or 'No status'}</span>",
            unsafe_allow_html=True,
        )
        close.button("✕ Close", key="cal_detail_close", use_container_width=True,
                     on_click=lambda: st.session_state.pop("cal_selected", None))
        def _field(slot, label, value):
            slot.markdown(f"<span style='color:#888;font-size:12px'>{label}</span><br>"
                          f"<b>{value or '—'}</b>", unsafe_allow_html=True)

        for start in range(0, len(fields), 3):   # a fresh row per 3 so rows stay aligned
            for slot, (label, value) in zip(st.columns(3), fields[start:start + 3]):
                _field(slot, label, value)
        for label, value in wide:
            _field(st, label, value)


def _render_day_table(day_df: pd.DataFrame, anchor: date, display_fn):
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
    now = _now()
    if "cal_jump" in st.session_state:
        _open_day(st.session_state.pop("cal_jump"))
    st.session_state.setdefault("cal_anchor", now.date())
    st.session_state.setdefault("cal_view", "Month")

    # --- Controls row ---
    c_today, c_prev, c_next, c_title, c_view = st.columns([1.3, 0.7, 0.7, 6, 2], vertical_alignment="center")
    c_today.button("📅 Today", key="cal_today", on_click=_go_today, use_container_width=True)
    c_prev.button("◀", key="cal_prev", on_click=_go, args=(-1,), use_container_width=True)
    c_next.button("▶", key="cal_next", on_click=_go, args=(1,), use_container_width=True)
    c_view.selectbox("View", VIEWS, key="cal_view", label_visibility="collapsed", on_change=_reset_clicks)

    view   = st.session_state.cal_view
    anchor = st.session_state.cal_anchor

    scope = st.radio("Show", ["All Records", "My Records"], horizontal=True,
                     key="cal_scope", label_visibility="collapsed")
    src   = df if scope == "All Records" or not username else df[df["Created_By"] == username]
    appts = _prepare(src)

    # --- Visible range + title ---
    if view == "Month":
        first = anchor.replace(day=1)
        last  = first.replace(day=pycal.monthrange(first.year, first.month)[1])
        title = anchor.strftime("%B %Y")
    elif view == "Week":
        first = anchor - timedelta(days=anchor.weekday())
        last  = first + timedelta(days=6)
        title = f"{first.strftime('%d %B')} – {last.strftime('%d %B, %Y')}"
    else:
        first = last = anchor
        title = anchor.strftime("%A, %d %B %Y")

    in_range = appts[(appts["_appt_date"] >= first) & (appts["_appt_date"] <= last)]
    c_title.markdown(
        f"<span style='font-size:22px;font-weight:600'>{title}</span>"
        f"<span style='color:#888;font-size:15px'> &nbsp;·&nbsp; {len(in_range)} appointment(s)</span>",
        unsafe_allow_html=True,
    )
    st.caption("🟡 Pending · 🔵 In Progress · 🟢 Completed · 🔴 Rejected — "
               "click a day to open it, click an appointment for its details.")

    # --- Calendar ---
    slot_min, slot_max = _slot_range(in_range)
    options = {
        "initialView":   FC_VIEW[view],
        "initialDate":   anchor.isoformat(),
        "headerToolbar": False,
        "timeZone":      "UTC",          # show stored wall-clock times as-is, no browser shift
        "now":           now.isoformat(timespec="seconds"),
        "firstDay":      1,
        "fixedWeekCount": False,         # only the weeks this month needs
        "height":        CAL_HEIGHT,     # fixed, Teams-style — Week/Day hours scroll inside
        "nowIndicator":  True,
        "eventDisplay":  "block",
        "dayMaxEvents":  3,
        "slotMinTime":   slot_min,
        "slotMaxTime":   slot_max,
        "slotDuration":  "00:30:00",
        "allDaySlot":    bool((in_range["_mins"] >= _NO_TIME).any()),
        "allDayText":    "No time",
        "eventTimeFormat": {"hour": "numeric", "minute": "2-digit", "meridiem": "short"},
        "slotLabelFormat": {"hour": "numeric", "meridiem": "short"},
        "views": {
            "dayGridMonth": {"dayHeaderFormat": {"weekday": "long"}},
            "timeGridWeek": {"dayHeaderFormat": {"weekday": "short", "day": "2-digit"}},
            "timeGridDay":  {"dayHeaderFormat": {"weekday": "long", "day": "2-digit", "month": "long"}},
        },
    }
    # streamlit-calendar measures its iframe height only once, on mount, so it starts at
    # height="0". The login CookieManager injects `.element-container:has(iframe[height="0"])
    # { display: none }` on every authenticated run, which hides the calendar before it can
    # size itself — it then stays blank forever. Exempt it from that rule and pin its height.
    st.markdown(
        "<style>"
        ".element-container:has(iframe[title*='streamlit_calendar']) { display: block !important; }"
        f"iframe[title*='streamlit_calendar'] {{ min-height: {CAL_HEIGHT + 10}px; }}"
        "</style>",
        unsafe_allow_html=True,
    )
    # Keyed on what is shown so every navigation mounts a fresh calendar at the right date
    # and a previous click result does not replay.
    state = fullcalendar(
        events=_to_events(in_range, view), options=options, custom_css=CUSTOM_CSS,
        callbacks=["dateClick", "eventClick"],
        key=f"fc_{view}_{anchor.isoformat()}_{scope}",
    )

    # The component keeps returning its last click on every rerun — act on each click once.
    cb = (state or {}).get("callback")
    if cb and state != st.session_state.get("cal_last_click"):
        st.session_state.cal_last_click = state
        if cb == "dateClick" and view != "Day":
            # The View selectbox is already drawn this run, so switch to Day at the start of the next one
            st.session_state.cal_jump = date.fromisoformat(state["dateClick"]["date"][:10])
            st.rerun()
        if cb == "eventClick":
            st.session_state.cal_selected = state["eventClick"]["event"]["id"]

    sel = st.session_state.get("cal_selected")
    if sel is not None and sel.isdigit() and int(sel) in appts.index:
        _render_details(appts.loc[int(sel)], display_fn)

    if view == "Day" and not in_range.empty:
        st.markdown("##### 📋 Appointments on this day")
        _render_day_table(in_range, anchor, display_fn)
