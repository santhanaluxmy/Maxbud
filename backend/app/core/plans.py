from app.core.config import get_settings

BASIC={"family_members":0,"receipt_scans":5,"advisor_messages":10,"active_goals":3,"active_reminders":10}
PREMIUM={"family_members":0,"receipt_scans":100,"advisor_messages":200,"active_goals":20,"active_reminders":None}
PLAN_LIMITS={
    "free":{**BASIC,"family_members":3}, # Grandfathered legacy accounts only.
    "premium":{**PREMIUM,"family_members":7},
    "trial":dict(BASIC),
    "premium_individual":dict(PREMIUM),
    "family_pack":{**PREMIUM,"family_members":get_settings().FAMILY_PACK_MEMBER_LIMIT},
    "read_only":{**BASIC,"receipt_scans":0,"advisor_messages":0,"active_goals":0,"active_reminders":0},
}
