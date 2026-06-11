"""
Generate realistic test data for DocRegistry Pro (for manual import into Google Sheets).

Run:
    python generate_test_data.py

Outputs (in the same folder):
    test_data_june2026.csv
    test_data_june2026.xlsx   (skipped if openpyxl is not installed)
"""

import random
from datetime import date, timedelta
import pandas as pd

# ── Configuration ────────────────────────────────────────────────
NUM_RECORDS = 50

ENTRY_DATE_START = date(2026, 6, 1)
ENTRY_DATE_END   = date(2026, 6, 11)   # today's date — adjust as needed

APPT_MONTH_START = date(2026, 6, 1)
APPT_MONTH_END   = date(2026, 6, 30)

DOC_TYPES = [
    "Sale Deed",
    "Lease Agreement",
    "Gift Deed",
    "Mortgage",
    "Power of Attorney",
    "Hak-Kami (Dispose of rights)",
    "Release",
    "Rent Agreement",
    "Agreement of Sale (Banakhat)",
]

# Weighted so most records are In Progress / Pending, but every status appears
STATUS_POOL = (
    ["In Progress"] * 9
    + ["Pending"] * 9
    + ["Completed"] * 5
    + ["Rejected"] * 2
)

SRO_OPTIONS = [
    "Ahmedabad- 1 City", "Ahmedabad- 2 Vadaj", "Ahmedabad- 3 Memnagar",
    "Ahmedabad- 4 Paldi", "Ahmedabad- 5 Narol", "Ahmedabad- 6 Naroda",
    "Ahmedabad- 7 Odhav", "Ahmedabad- 8 Sola", "Ahmedabad- 9 Bopal",
    "Ahmedabad- 10 Vejalpur", "Ahmedabad- 11 Aslali", "Ahmedabad- 12 Nikol",
    "Ahmedabad- 13 Sabarmati", "Ahmedabad- 13 City Agriculture",
    "Ahmedabad- 14 Vastral", "Ahmedabad- 14 Dascroi Agriculture",
    "S.R.O.- Sanand", "S.R.O.- Viramgam", "S.R.O.- Dholka",
    "S.R.O.-Dhandhuka", "S.R.O.- Bavla", "S.R.O.- Mandal",
    "S.R.O.- Detroj", "S.R.O.- Dholera",
    "Gandhinagar Zone- 1", "Gandhinagar Zone- 2", "Gandhinagar Zone- 3",
    "S.R.O- Dehgam", "S.R.O- Mansa", "S.R.O- Kalol",
    "S.R.O.- Kheralu", "S.R.O.- Kadi", "S.R.O.- Visnagar",
    "S.R.O.- Unjha", "S.R.O.- Vijapur", "S.R.O.- Mahesana",
    "S.R.O.- Satlasan", "S.R.O.- Becharaji", "S.R.O.- Vadnagar",
    "S.R.O.- Jotana",
]

PARTY2_OPTIONS = [
    "NCB NARODA", "NCB NANA CHILODA", "NCB NAVRANGPURA", "NCB NARANPURA",
    "NCB DARIYAPUR", "NCB RAKHIYAL", "NCB SOLA", "NCB RANIP",
    "NCB KATHWADA", "NCB MEGHANINAGAR", "NCB SABARMATI", "NCB KOBA",
    "NCB SATELLITE", "NCB NAVA NARODA",
    "Vijay Co-oprative Bank (VCB)", "Amdvad Distrcit Co-oprative Bank (ADC)",
]

CREATED_BY = ["admin", "achyutam", "Akhilb"]

FIRST_NAMES_MALE = [
    "Rajesh", "Sunil", "Mahesh", "Dinesh", "Naresh", "Ramesh", "Suresh",
    "Kiran", "Jignesh", "Hardik", "Bhavesh", "Chirag", "Nitin", "Sandeep",
    "Vipul", "Ashok", "Ketan", "Paresh", "Manoj", "Yogesh", "Vikram",
    "Pravin", "Tushar", "Kalpesh", "Mehul", "Jayesh", "Alpesh", "Nilesh",
]

FIRST_NAMES_FEMALE = [
    "Priya", "Sunita", "Hetal", "Pooja", "Bhavna", "Rekha", "Nisha",
    "Geeta", "Kavita", "Mona", "Hansa", "Foram", "Jyoti", "Komal",
    "Urvashi", "Trupti", "Nidhi", "Falguni", "Reema", "Shilpa",
]

MIDDLE_NAMES = [
    "Kumar", "Ramesh", "Suresh", "Dinesh", "Bhavesh", "Kantilal", "Babubhai",
    "Navinbhai", "Hasmukh", "Prakash", "Jitendra", "Manish", "Nilesh",
    "Mahendra", "Arvindbhai", "Kiritbhai", "Dipak", "Niranjan", "Chirag",
    "Girishbhai", "Rasiklal",
]

LAST_NAMES = [
    "Patel", "Shah", "Mehta", "Desai", "Joshi", "Trivedi", "Solanki",
    "Parikh", "Modi", "Vyas", "Gohil", "Nayak", "Dave", "Gadhvi",
    "Panchal", "Bhatt", "Kapoor", "Chauhan", "Raval", "Thakkar",
    "Pandya", "Vora", "Doshi", "Shroff", "Mistry",
]


def random_date(start: date, end: date) -> date:
    delta_days = (end - start).days
    return start + timedelta(days=random.randint(0, delta_days))


def random_name() -> str:
    first = random.choice(FIRST_NAMES_MALE if random.random() < 0.55 else FIRST_NAMES_FEMALE)
    return f"{first} {random.choice(MIDDLE_NAMES)} {random.choice(LAST_NAMES)}"


def random_mobile() -> str:
    return "9" + "".join(str(random.randint(0, 9)) for _ in range(9))


def random_appointment_time() -> str:
    hour = random.randint(9, 17)
    minute = random.choice([0, 15, 30, 45])
    return f"{hour:02d}:{minute:02d}:00"


def build_records(n: int):
    records = []
    used_ids = set()

    # cycle doc types so every type is represented, then shuffle
    doc_type_cycle = (DOC_TYPES * (n // len(DOC_TYPES) + 1))[:n]
    random.shuffle(doc_type_cycle)

    for i in range(n):
        seq = i + 1

        entry_date = random_date(ENTRY_DATE_START, ENTRY_DATE_END)
        entry_date_str = entry_date.strftime("%Y%m%d")

        # ensure a unique Entry_ID (Entry_Date + Entry_Time, no separators)
        while True:
            entry_time_str = (
                f"{random.randint(9, 18):02d}"
                f"{random.randint(0, 59):02d}"
                f"{random.randint(0, 59):02d}"
            )
            entry_id = f"{entry_date_str}{entry_time_str}"
            if entry_id not in used_ids:
                used_ids.add(entry_id)
                break

        entry_time_fmt = f"{entry_time_str[0:2]}:{entry_time_str[2:4]}:{entry_time_str[4:6]}"

        appt_date = random_date(APPT_MONTH_START, APPT_MONTH_END)

        record = {
            "Entry_ID": entry_id,
            "Doc_Type": doc_type_cycle[i],
            "Appointment Date": appt_date.strftime("%Y-%m-%d"),
            "Appointment Time": random_appointment_time(),
            "SRO": random.choice(SRO_OPTIONS),
            "Party_Name 1": random_name(),
            "Party_Name 1 Mobile_No": random_mobile(),
            "Party_Name 2": random.choice(PARTY2_OPTIONS),
            "Garvi_Application_ID": f"{entry_date_str}001{seq:03d}",
            "Inedex_Application_No": f"{entry_date_str}002{seq:03d}",
            "Index_No": f"IDX-{seq:03d}-2026",
            "Search_No": f"SRH-{seq:03d}-2026",
            "Title_Status": random.choice(STATUS_POOL),
            "Created_By": random.choice(CREATED_BY),
            "Entry_Date": entry_date.strftime("%Y-%m-%d"),
            "Entry_Time": entry_time_fmt,
        }
        records.append(record)

    return records


def main():
    records = build_records(NUM_RECORDS)
    df = pd.DataFrame(records)
    df = df.sort_values(by=["Entry_Date", "Entry_Time"]).reset_index(drop=True)

    csv_path = "test_data_june2026.csv"
    df.to_csv(csv_path, index=False)
    print(f"Wrote {len(df)} records to {csv_path}")

    try:
        xlsx_path = "test_data_june2026.xlsx"
        df.to_excel(xlsx_path, index=False)
        print(f"Wrote {len(df)} records to {xlsx_path}")
    except ImportError:
        print("openpyxl not installed - skipping .xlsx output.")
        print("Install it with: pip install openpyxl")


if __name__ == "__main__":
    main()
