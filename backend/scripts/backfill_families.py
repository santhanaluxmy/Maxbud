"""Opt-in data-only backfill. Dry run by default; never run during login."""
import argparse
from sqlalchemy import exists, select
from app.database import SessionLocal
from app.models.family import Family, FamilyMembership, Subscription
from app.models.user import User
from app.services.family import create_owner_family


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Create missing family relationships in one transaction")
    args = parser.parse_args()
    with SessionLocal() as db:
        # Skip anyone with any membership history, including removed members.
        statement = select(User).where(
            User.is_active.is_(True), User.role == "user",
            ~exists().where(Family.owner_user_id == User.id),
            ~exists().where(FamilyMembership.user_id == User.id),
            ~exists().where(Subscription.user_id == User.id),
        ).order_by(User.id).with_for_update()
        users = list(db.scalars(statement).all())
        print(f"Eligible legacy accounts: {len(users)}; user IDs: {[u.id for u in users]}")
        if not args.apply:
            print("Dry run: no changes. Review and rerun with --apply to create Free/LKR families.")
            db.rollback()
            return
        try:
            for user in users:
                create_owner_family(db, user)
            db.commit()
            print(f"Created {len(users)} families. Financial records unchanged.")
        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()
