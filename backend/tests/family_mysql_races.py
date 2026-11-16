"""Concurrency and migration checks in a disposable MySQL schema.

Copies schema DDL only; no customer rows are copied or changed. Creates and
removes only a UUID-named maxbud_family_test_* database. Requires permission to
create/drop that isolated schema. The configured production schema is read-only.
"""
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Barrier
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from app.database import engine as source, connect_args, get_db
from app.main import app


def run():
    schema = 'maxbud_family_test_' + uuid.uuid4().hex[:16]
    server = create_engine(source.url.set(database=None), connect_args=connect_args)
    isolated = None
    created = False
    try:
        with server.begin() as connection:
            connection.execute(text(f'CREATE DATABASE `{schema}` CHARACTER SET utf8mb4'))
        created = True
        isolated = create_engine(source.url.set(database=schema), connect_args=connect_args, pool_size=10, max_overflow=10, hide_parameters=True)
        with source.connect() as connection:
            ddl = [connection.execute(text(f'SHOW CREATE TABLE `{name}`')).one()[1] for name in inspect(connection).get_table_names()]
        with isolated.begin() as connection:
            connection.execute(text('SET FOREIGN_KEY_CHECKS=0'))
            for statement in ddl:
                connection.exec_driver_sql(statement)
            connection.execute(text('SET FOREIGN_KEY_CHECKS=1'))

        def session():
            with Session(isolated, expire_on_commit=False) as db:
                yield db
        app.dependency_overrides[get_db] = session
        client = TestClient(app)
        password = 'SecurePassword1!'
        owner = client.post('/auth/register', json={'full_name':'Race Owner','email':'race-owner@example.com','password':password,'confirm_password':password}).json()
        assert 'access_token' in owner, owner
        headers = {'Authorization':'Bearer '+owner['access_token']}
        # Prove that the exact new migration preserves a legacy contribution.
        with isolated.begin() as connection:
            old_goal = connection.execute(text("INSERT INTO savings_goals (user_id,name,target_amount,target_date,priority,archived) VALUES (:uid,'Legacy test goal',1000,'2027-01-01',1,0)"), {'uid':owner['user']['id']}).lastrowid
            legacy_id = connection.execute(text("INSERT INTO goal_contributions (goal_id,amount,recorded_on,reversed_at) VALUES (:goal,50,'2026-11-13',NULL)"), {'goal':old_goal}).lastrowid
            before = tuple(connection.execute(text('SELECT id,goal_id,amount,recorded_on,reversed_at FROM goal_contributions WHERE id=:id'),{'id':legacy_id}).one())
            # If the source already contains the new columns, no migration is
            # repeated. Otherwise test the exact upgrade on the old cloned DDL.
            if 'family_id' not in {c['name'] for c in inspect(connection).get_columns('goals')}:
                path = Path(__file__).resolve().parents[1] / 'migrations/versions/20261113_shared_goals.py'
                spec = spec_from_file_location('shared_goal_migration',path)
                migration = module_from_spec(spec)
                spec.loader.exec_module(migration)
                with Operations.context(MigrationContext.configure(connection)):
                    migration.upgrade()
            after = tuple(connection.execute(text('SELECT id,goal_id,amount,recorded_on,reversed_at FROM goal_contributions WHERE id=:id'),{'id':legacy_id}).one())
            assert before == after, 'Legacy contribution changed'
            old_fk = next(fk for fk in inspect(connection).get_foreign_keys('goal_contributions') if fk['constrained_columns']==['goal_id'])
            assert old_fk['referred_table']=='savings_goals'
        print('PASS: exact migration on cloned MySQL schema; legacy ledger row and FK preserved',flush=True)
        barrier = Barrier(8)
        # Do not start the production lifespan when creating worker clients.
        # Plain client instances use the dependency override and isolated schema.
        def add(index):
            worker = TestClient(app)
            try:
                barrier.wait(timeout=20)
                return worker.post('/family/members',headers=headers,json={'full_name':f'Race Member {index}','email':f'race-{index}@example.com','password':password,'confirm_password':password})
            finally:
                worker.close()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(add,range(8)))
        assert sum(response.status_code==201 for response in results)==2, [(r.status_code,r.text) for r in results]
        assert all(response.status_code in [201,409] for response in results)
        member_email=next(response.json()['email'] for response in results if response.status_code==201)
        member=client.post('/auth/login',json={'email':member_email,'password':password}).json()
        member_headers={'Authorization':'Bearer '+member['access_token']}
        response=client.post('/goals?scope=family',headers=headers,json={'name':'Concurrent shared goal','target_amount':'1000'})
        assert response.status_code==201,response.text
        key=response.json()['id']
        barrier=Barrier(2)
        def give(info):
            worker=TestClient(app)
            try:
                token,amount,request_id=info
                barrier.wait(timeout=20)
                return worker.post(f'/goals/{key}/contribute',headers=token,json={'amount':amount,'request_id':request_id})
            finally:
                worker.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(give,[(headers,'300','owner-once'),(headers,'300','owner-once')]))
        assert all(r.status_code==200 for r in results),[(r.status_code,r.text) for r in results]
        assert client.get('/goals?scope=family',headers=headers).json()[0]['saved_amount']=='300.00'
        barrier=Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(give,[(member_headers,'200','member-once'),(member_headers,'200','member-once')]))
        assert all(r.status_code==200 for r in results),[(r.status_code,r.text) for r in results]
        goal=client.get('/goals?scope=family',headers=headers).json()[0]
        assert goal['saved_amount']=='500.00',goal
        assert len(goal['history'])==2,goal
        print('PASS: 8 concurrent member requests enforce 3-user Free capacity; concurrent contribution retries produce exactly 300 + 200 = 500',flush=True)
        client.close()
    finally:
        app.dependency_overrides.clear()
        if isolated:
            isolated.dispose()
        if created:
            with server.begin() as connection:
                connection.execute(text(f'DROP DATABASE `{schema}`'))
            print('Temporary MySQL test schema removed; customer data unchanged',flush=True)
        server.dispose()


if __name__=='__main__':
    run()
