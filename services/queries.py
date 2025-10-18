import pandas as pd
from datetime import date
from .supabase_client import get_supabase

def get_role_by_email(email: str) -> str:
    sb = get_supabase()
    r = sb.table("user_roles_view").select("role").eq("email", email).limit(1).execute()
    if r.data:
        return r.data[0]["role"]
    return "viewer"

def fetch_kpis(start: date, end: date, org_unit: str | None = None) -> pd.DataFrame:
    sb = get_supabase()
    q = sb.table("kpi_facts_view").select("*").gte("date", str(start)).lte("date", str(end))
    if org_unit:
        q = q.eq("org_unit", org_unit)
    data = q.execute().data
    return pd.DataFrame(data)

def fetch_adjustments(start: date, end: date) -> pd.DataFrame:
    sb = get_supabase()
    data = (sb.table("adjustments")
              .select("*")
              .gte("date", str(start))
              .lte("date", str(end))
              .order("date", desc=False)
              .execute().data)
    return pd.DataFrame(data)

def upsert_adjustments(rows: list[dict]) -> None:
    if not rows:
        return
    sb = get_supabase()
    # Upsert by (date, org_unit, kpi_name) composite key; adjust to your PK
    sb.table("adjustments").upsert(rows).execute()
