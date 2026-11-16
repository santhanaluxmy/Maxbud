"""Opt-in real provider verification. MySQL mode uses only an outer rollback.
Run FAMILY_TEST_MYSQL=1 PYTHONPATH=.:tests .venv/bin/python tests/live_groq.py.
Consumes two real Groq requests; no customer financial records persist.
"""
import json
from pathlib import Path
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import patch
import test_family
from app.core.config import get_settings


def run():
    case=test_family.FamilyTests('test_registration_overview_and_refresh')
    case.setUp()
    try:
        auth=case.client.post('/auth/register',json=case.payload('live-groq')).json()
        headers=case.headers(auth)
        account=case.client.post('/accounts',headers=headers,json={'name':'Live verification cash','kind':'cash','opening_balance':'10000'}).json()
        assert 'id' in account
        budget=case.client.post('/budgets',headers=headers,json={'category':'Food','monthly_limit':'5000'})
        assert budget.status_code==201,budget.text
        with TemporaryDirectory(prefix='maxbud-live-receipts-') as directory,patch.object(get_settings(),'RECEIPT_STORAGE_DIR',directory):
            image=Path(__file__).resolve().parents[1]/'sample_receipt.jpg'
            response=case.client.post('/ai/receipts',headers=headers,files={'file':('receipt.jpg',image.read_bytes(),'image/jpeg')})
            assert response.status_code==201,response.text
            scan=response.json();data=scan['data']
            assert data['printed_total'] is None,'Cropped reference receipt has no printed grand total'
            assert data['category']=='Food'
            assert len(data['items'])>=1
            subtotal=sum((Decimal(str(item['amount'])) for item in data['items'] if item['amount'] is not None),Decimal(0))
            assert subtotal>0
            # Reference reviewed by the operator: visible item subtotal is used
            # explicitly for this test, never labelled a printed grand total.
            reviewed=data|{'merchant':data['merchant'] or 'Reviewed shop','date':data['date'] or '2026-11-11','currency':'LKR','total':str(subtotal),'account_id':account['id']}
            saved=case.client.post(f"/ai/receipts/{scan['id']}/confirm",headers=headers,json=reviewed)
            assert saved.status_code==200,saved.text
            repeat=case.client.post(f"/ai/receipts/{scan['id']}/confirm",headers=headers,json=reviewed)
            assert repeat.json()['transaction_id']==saved.json()['transaction_id']
            txns=case.client.get('/transactions',headers=headers).json()
            assert len(txns)==1 and Decimal(txns[0]['amount'])==subtotal
            balances=case.client.get('/accounts',headers=headers).json()
            assert Decimal(balances['items'][0]['current_balance'])==Decimal('10000')-subtotal
            assert Decimal(case.client.get('/budgets',headers=headers).json()[0]['spent'])==subtotal
            reply=case.client.post('/ai/advisor',headers=headers,json={'question':'Can I spend LKR 5000 on shopping? Use my recorded balance, expense and Food budget. Briefly explain in English and Tamil.','request_id':'live-advisor'})
            assert reply.status_code==200,reply.text
            assert len(reply.json()['answer'])>20
            assert len(case.client.get('/ai/advisor',headers=headers).json())==1
            used=case.client.get('/ai/usage',headers=headers).json()['used']
            assert used=={'receipt_scans':1,'advisor_messages':1}
            print(json.dumps({'provider':'Groq LIVE (not mocked)','vision_model':get_settings().GROQ_VISION_MODEL,'chat_model':get_settings().GROQ_CHAT_MODEL,'printed_total':None,'items_extracted':len(data['items']),'calculated_subtotal':str(subtotal),'confirmed_once':True,'balance_and_budget_exact':True,'advisor_history_saved':True,'usage':used,'database':'MySQL outer rollback' if test_family.MYSQL else 'temporary SQLite'},ensure_ascii=False))
    finally:
        case.tearDown();case.doCleanups()


if __name__=='__main__':run()
