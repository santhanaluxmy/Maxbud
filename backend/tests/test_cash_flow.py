"""Read-only report contracts; SQLite or the inspected MySQL outer rollback."""
import unittest
from datetime import date, datetime
from decimal import Decimal
import test_family
from app.models.finance import Account, Transaction, Goal

class CashFlowTests(test_family.FamilyTests):
    def test_brought_forward_transfers_shared_payments_archives_and_privacy(self):
        uid=self.owner['user']['id']
        cash=Account(user_id=uid,name='Cash',kind='cash',currency='LKR',opening_balance=1000)
        old=Account(user_id=uid,name='Old account',kind='bank',currency='LKR',opening_balance=200,is_archived=True)
        secret=Account(user_id=self.other['user']['id'],name='SECRET ACCOUNT',kind='cash',currency='LKR',opening_balance=999999)
        self.db.add_all([cash,old,secret]);self.db.flush()
        family=self.get('/family').json()['id']
        entries=[(cash,'income',300,date(2026,10,30),'Brought forward',None,None),
                 (cash,'income',800,date(2026,11,1),'Salary',None,None),
                 (cash,'expense',50,date(2026,11,3),'Groceries',None,None),
                 (cash,'transfer_out',100,date(2026,11,4),'Transfer out',None,None),
                 (old,'transfer_in',100,date(2026,11,4),'Transfer in',None,None),
                 (cash,'transfer_out',200,date(2026,11,5),'Wallet funding',None,None),
                 (cash,'expense',120,date(2026,11,6),'Shared electricity',family,None),
                 (cash,'transfer_in',60,date(2026,11,7),'Reimbursement',None,None),
                 (cash,'expense',999,date(2026,11,8),'Deleted',None,datetime(2026,11,9)),
                 (cash,'income',10,date(2026,12,1),'Next month',None,None),
                 (secret,'income',777777,date(2026,11,1),'PRIVATE SALARY',None,None)]
        for a,k,v,d,n,f,deleted in entries:self.db.add(Transaction(user_id=a.user_id,account_id=a.id,kind=k,category='Food',amount=v,txn_date=d,description=n,family_id=f,deleted_at=deleted))
        self.db.add(Goal(user_id=uid,name='Allocation',target_amount=1000,saved_amount=500,status='active'));self.db.commit()
        response=self.get('/dashboard?year=2026&month=11&include_cash_flow=true')
        self.assertEqual(response.status_code,200,response.text)
        self.assertNotIn('PRIVATE SALARY',response.text);self.assertNotIn('SECRET ACCOUNT',response.text)
        report=response.json()['cash_flow']
        self.assertEqual(Decimal(report['opening_balance']),1500)
        self.assertEqual([Decimal(r['running_balance']) for r in report['rows']],[2300,2250,2150,2250,2050,1930,1990])
        self.assertEqual((Decimal(report['income']),Decimal(report['expense']),Decimal(report['net_cash_flow'])),(800,170,630))
        self.assertEqual(Decimal(response.json()['active_tracked_balance']),1700)
        self.assertEqual(response.json()['monthly_expenses'],'50.00')
        self.assertTrue(all(r['income'] is None and r['expense'] is None for r in report['rows'] if r['kind'].startswith('transfer')))
        self.assertTrue(report['rows'][5]['shared_payment'])
        self.assertEqual(len(self.get('/transactions').json()),4)

    def test_empty_month_opt_in_and_period_validation(self):
        self.db.add(Account(user_id=self.owner['user']['id'],name='Cash',kind='cash',currency='LKR',opening_balance=Decimal('25.10')));self.db.commit()
        self.assertNotIn('cash_flow',self.get('/dashboard').json())
        report=self.get('/dashboard?year=2026&month=9&include_cash_flow=true').json()['cash_flow']
        self.assertEqual(report['rows'],[])
        self.assertEqual(Decimal(report['opening_balance']),Decimal('25.10'))
        self.assertEqual(report['opening_balance'],report['closing_balance'])
        self.assertEqual(self.get('/dashboard?month=13&include_cash_flow=true').status_code,422)
        self.assertIn(self.client.get('/dashboard?include_cash_flow=true').status_code,[401,403])

def load_tests(loader,tests,pattern):
    return unittest.TestSuite(CashFlowTests(name) for name in CashFlowTests.__dict__ if name.startswith('test_'))
