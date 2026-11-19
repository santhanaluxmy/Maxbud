"""Invitation lifecycle and email submission; disposable SQLite, mocked SMTP."""
from datetime import timedelta
import hashlib
import secrets
import json
import smtplib
import unittest
from unittest.mock import patch

from sqlalchemy import select, func

import test_family
from app.core.config import get_settings
from app.models.family import Family, FamilyMembership
from app.models.finance import Account, Transaction
from app.models.platform import FamilyInvitation, PlatformEvent
from app.models.user import now_utc
from app.services import invitations as delivery


class FamilyInvitationTests(unittest.TestCase):
    for _name in ['setUp', 'tearDown', 'close_mysql', 'email', 'payload', 'register', 'headers', 'get', 'enable_family_pack']:
        locals()[_name] = getattr(test_family.FamilyTests, _name)

    def setUp(self):
        test_family.FamilyTests.setUp(self)
        self.enable_family_pack()
        settings = patch.multiple(get_settings(), PUBLIC_FRONTEND_URL='https://maxbud.example.com',
                                  SMTP_HOST='smtp.example.com', SMTP_FROM='maxbud@example.com', SMTP_USERNAME='synthetic', SMTP_PASSWORD='synthetic')
        settings.start(); self.addCleanup(settings.stop)

    def post(self, path, body=None, person=None):
        return self.client.post(path, json=body, headers=self.headers(person or self.owner))

    def invite(self, name='member'):
        return self.post('/family/invitations', {'email':self.email(name), 'can_view_shared':True, 'can_add_shared':True})

    def fresh(self, name='member'):
        response=self.client.post('/auth/register',json=self.payload(name))
        self.assertEqual(response.status_code,201,response.text)
        return response.json()

    def test_unconfigured_smtp_fails_clearly_without_creating_invitation(self):
        before = self.db.scalar(select(func.count(FamilyInvitation.id)))
        with patch.object(get_settings(), 'SMTP_HOST', ''), patch('app.services.invitations.send_invitation', return_value='<synthetic@example.com>') as send:
            response = self.invite()
        self.assertEqual(response.status_code, 503, response.text)
        self.assertIn('SMTP', response.json()['detail'])
        self.assertEqual(self.db.scalar(select(func.count(FamilyInvitation.id))), before)
        send.assert_not_called()

    def test_configured_smtp_submits_once_and_no_token_in_audit(self):
        with patch('app.services.invitations.configured',return_value=True), patch('app.services.invitations.send_invitation', return_value='<synthetic@example.com>') as send:
            result=self.invite().json()
            self.assertEqual(self.invite().status_code,409)
        self.assertEqual(result['delivery_status'],'submitted')
        send.assert_called_once()
        self.assertEqual(send.call_args.args[0],self.email('member'))
        self.assertEqual(send.call_args.kwargs['url'],result['invitation_url'])
        self.assertEqual(self.get('/family/invitations').json()[0]['delivery_status'],'submitted')
        events=self.db.scalars(select(PlatformEvent).where(PlatformEvent.kind=='family_invitation_email')).all()
        self.assertNotIn(result['token'],json.dumps([row.details for row in events]))

    def test_failed_smtp_preserves_invitation_and_can_resend_without_another_seat(self):
        with patch('app.services.invitations.send_invitation', side_effect=smtplib.SMTPAuthenticationError(535, b'private provider detail')):
            response = self.invite()
        self.assertEqual(response.status_code, 502, response.text)
        self.assertIn('authentication', response.json()['detail'])
        self.assertNotIn('private provider detail', response.text)
        row = self.db.scalar(select(FamilyInvitation).where(FamilyInvitation.email == self.email('member')))
        old_hash = row.token_hash
        self.assertEqual(row.status, 'pending')
        self.assertEqual(self.get('/family/invitations').json()[0]['delivery_status'], 'failed')
        before = self.db.scalar(select(func.count(FamilyInvitation.id)))
        member = self.fresh()
        self.assertEqual(self.post(f'/family/invitations/{row.id}/resend', person=member).status_code, 403)
        with patch('app.services.invitations.send_invitation', return_value='<resent@example.com>') as send:
            resent = self.post(f'/family/invitations/{row.id}/resend')
            self.assertEqual(resent.status_code, 200, resent.text)
            self.assertEqual(self.post(f'/family/invitations/{row.id}/resend').status_code, 429)
            send.assert_called_once()
        self.assertNotEqual(row.token_hash, old_hash)
        self.assertEqual(self.db.scalar(select(func.count(FamilyInvitation.id))), before)
        self.assertEqual(self.post('/family/invitations/respond', {'token': resent.json()['token'], 'accept': True}, member).status_code, 200)

    def test_failed_resend_preserves_the_existing_link_expiry_and_reserved_seat(self):
        original = self.invite().json()
        row = self.db.get(FamilyInvitation, original['id'])
        original_hash, original_expiry = row.token_hash, row.expires_at
        events = self.db.scalars(select(PlatformEvent).where(PlatformEvent.kind == 'family_invitation_email', PlatformEvent.target == str(row.id))).all()
        for event in events:
            event.created_at = now_utc() - timedelta(minutes=2)
        self.db.commit()
        count = self.db.scalar(select(func.count(FamilyInvitation.id)))
        slots = self.get('/family').json()['available_slots']
        with patch('app.services.invitations.send_invitation', side_effect=smtplib.SMTPAuthenticationError(535, b'private provider detail')):
            response = self.post(f'/family/invitations/{row.id}/resend')
        self.assertEqual(response.status_code, 502, response.text)
        self.assertNotIn('private provider detail', response.text)
        self.db.refresh(row)
        self.assertEqual((row.token_hash, row.expires_at, row.status), (original_hash, original_expiry, 'pending'))
        self.assertEqual(self.db.scalar(select(func.count(FamilyInvitation.id))), count)
        self.assertEqual(self.get('/family').json()['available_slots'], slots)
        event = self.db.scalar(select(PlatformEvent).where(PlatformEvent.kind == 'family_invitation_email', PlatformEvent.target == str(row.id)).order_by(PlatformEvent.id.desc()))
        self.assertEqual(event.details['smtp_code'], 535)
        member = self.fresh()
        self.assertEqual(self.post('/family/invitations/respond', {'token': original['token'], 'accept': True}, member).status_code, 200)

    def test_public_preview_acceptance_count_permissions_privacy_and_login(self):
        invitation=self.invite().json();member=self.fresh()
        preview=self.client.post('/family/invitations/preview',json={'token':invitation['token']})
        self.assertEqual(preview.status_code,200,preview.text)
        self.assertEqual(preview.json()['invited_email'],self.email('member'))
        for value in ['token_hash','account_id','password','subscription','transactions']:
            self.assertNotIn(value,preview.text)
        account=self.post('/accounts',{'name':'PRIVATE OWNER ACCOUNT','kind':'cash','opening_balance':'5000'}).json()
        self.assertEqual(self.post('/family/invitations/respond',{'token':invitation['token'],'accept':True},self.other).status_code,403)
        for _ in range(2):
            self.assertEqual(self.post('/family/invitations/respond',{'token':invitation['token'],'accept':True},member).status_code,200)
        self.assertEqual(self.get('/family').json()['total_active_members'],2)
        wallet=self.post('/family/wallets',{'name':'Common wallet'}).json()['id']
        self.assertEqual(self.post('/family/income',{'account_id':wallet,'category':'Shared','amount':'100','request_id':'member-income'},member).status_code,201)
        self.assertEqual(self.get('/dashboard?scope=family',member).json()['monthly_income'],'100.00')
        self.assertNotIn('PRIVATE OWNER ACCOUNT',self.get('/dashboard?scope=family',member).text)
        self.assertEqual(self.get(f"/accounts/{account['id']}",member).status_code,404)
        login=self.client.post('/auth/login',json={'email':self.email('member'),'password':'SecurePassword1!'}).json()
        self.assertTrue(login['has_household'])
        self.assertFalse(login['onboarding_completed'])
        self.assertEqual(self.get('/family',login).json()['role'],'member')
        self.assertEqual(self.get('/family/invitations').json()[0]['status'],'accepted')

    def test_invalid_expired_revoked_and_removed_member_cannot_join(self):
        member=self.fresh()
        self.assertEqual(self.client.post('/family/invitations/preview',json={'token':'x'*43}).status_code,404)
        for state in ['expired','revoked']:
            invitation=self.invite().json()
            row=self.db.get(FamilyInvitation,invitation['id'])
            if state=='expired':row.expires_at=now_utc()-timedelta(seconds=1)
            else:self.client.delete(f"/family/invitations/{row.id}",headers=self.headers(self.owner))
            self.db.commit()
            self.assertEqual(self.client.post('/family/invitations/preview',json={'token':invitation['token']}).json()['status'],state)
            self.assertEqual(self.post('/family/invitations/respond',{'token':invitation['token'],'accept':True},member).status_code,409)
        invitation=self.invite().json()
        self.post('/family/invitations/respond',{'token':invitation['token'],'accept':True},member)
        self.client.delete(f"/family/members/{member['user']['id']}",headers=self.headers(self.owner))
        self.assertEqual(self.post('/family/invitations/respond',{'token':invitation['token'],'accept':True},member).status_code,409)

    def test_four_invited_members_and_pending_reservations_enforce_five_seats(self):
        initial = self.get('/family').json()
        self.assertEqual((initial['total_active_members'], initial['max_members'], initial['available_slots']), (1, 5, 4))
        self.assertEqual(self.get('/subscriptions').json()['limits']['family_members'], 5)
        invitations = []
        for index in range(4):
            result = self.invite('member' + str(index))
            self.assertEqual(result.status_code, 201, result.text)
            invitations.append(result.json())
            state = self.get('/family').json()
            self.assertEqual((state['total_active_members'], state['reserved_slots'], state['available_slots']), (1, index + 1, 3 - index))
        self.assertEqual(self.invite('overflow').status_code, 409)
        # An invitation issued under the old six-person limit must survive,
        # but its acceptance must not create a sixth active membership.
        token = secrets.token_urlsafe(32)
        legacy = FamilyInvitation(family_id=initial['id'], invited_by=self.owner['user']['id'],
                                  email=self.email('legacy-extra'), token_hash=hashlib.sha256(token.encode()).hexdigest(),
                                  expires_at=now_utc() + timedelta(days=1), can_view_shared=True, can_add_shared=True)
        self.db.add(legacy)
        self.db.commit()
        for index, invitation in enumerate(invitations):
            person = self.fresh('member' + str(index))
            accepted = self.post('/family/invitations/respond', {'token': invitation['token'], 'accept': True}, person)
            self.assertEqual(accepted.status_code, 200, accepted.text)
            self.assertEqual(self.post('/family/invitations/respond', {'token': invitation['token'], 'accept': True}, person).status_code, 200)
        full = self.get('/family').json()
        self.assertEqual((full['total_active_members'], full['max_members'], full['available_slots']), (5, 5, 0))
        extra = self.fresh('legacy-extra')
        self.assertEqual(self.post('/family/invitations/respond', {'token': token, 'accept': True}, extra).status_code, 409)
        self.assertEqual(self.db.get(FamilyInvitation, legacy.id).status, 'pending')
        self.assertEqual(self.get('/family').json()['total_active_members'], 5)
        self.assertEqual(self.invite('sixth').status_code, 409)
        self.assertEqual(self.db.scalar(select(func.count(FamilyInvitation.id)).where(FamilyInvitation.family_id == initial['id'])), 5)

    def test_revoked_pending_invitation_releases_one_of_four_member_slots(self):
        invitations = [self.invite('reserved' + str(index)).json() for index in range(4)]
        self.assertEqual(self.get('/family').json()['available_slots'], 0)
        self.assertEqual(self.client.delete(f"/family/invitations/{invitations[0]['id']}", headers=self.headers(self.owner)).status_code, 200)
        self.assertEqual(self.get('/family').json()['available_slots'], 1)
        self.assertEqual(self.invite('replacement').status_code, 201)
        self.assertEqual(self.get('/family').json()['available_slots'], 0)

    def test_closing_empty_household_revokes_pending_links_without_deleting_personal_data(self):
        invitation=self.invite().json()
        self.post('/accounts',{'name':'Personal history','kind':'cash','opening_balance':'1'})
        self.assertEqual(self.post('/family/close').status_code,200)
        self.assertEqual(self.db.get(FamilyInvitation,invitation['id']).status,'revoked')
        self.assertEqual(self.client.post('/family/invitations/preview',json={'token':invitation['token']}).status_code,410)
        self.assertEqual(len(self.get('/accounts').json()['items']),1)
        self.assertEqual(self.post('/family',{'name':'Reopened household'}).status_code,201)
        member=self.fresh()
        self.assertEqual(self.post('/family/invitations/respond',{'token':invitation['token'],'accept':True},member).status_code,409)

    def test_close_refuses_shared_records_and_non_owner(self):
        invitation=self.invite().json();member=self.fresh()
        self.post('/family/invitations/respond',{'token':invitation['token'],'accept':True},member)
        self.assertEqual(self.post('/family/close',person=member).status_code,403)
        self.client.delete(f"/family/members/{member['user']['id']}",headers=self.headers(self.owner))
        self.post('/family/budgets',{'category':'Food','monthly_limit':'100'})
        self.assertEqual(self.post('/family/close').status_code,409)
        self.assertTrue(self.db.scalar(select(Family).where(Family.owner_user_id==self.owner['user']['id'])).is_active)

    def test_public_url_validation_and_deployment_origin(self):
        with patch.object(get_settings(), 'PUBLIC_FRONTEND_URL', 'https://maxbud.example.com/'):
            result = self.invite().json()
            self.assertTrue(result['invitation_url'].startswith('https://maxbud.example.com/invite#invite='))
            self.assertFalse(result['is_local_url'])
        before = self.db.scalar(select(func.count(FamilyInvitation.id)))
        for url in ['', 'http://localhost:5173', 'https://localhost', 'https://localhost.', 'https://127.0.0.1', 'https://10.0.0.1', 'https://[::1]', 'https://192.168.1.10', 'https://app.local', 'javascript:alert(1)', 'https://user:secret@example.com', 'https://example.com/path', 'https://example.com?next=bad']:
            with self.subTest(url=url), patch.object(get_settings(), 'PUBLIC_FRONTEND_URL', url):
                self.assertEqual(self.invite('another').status_code, 503)
        self.assertEqual(self.db.scalar(select(func.count(FamilyInvitation.id))), before)


class InvitationSMTPTests(unittest.TestCase):
    def setUp(self):
        email_reader = patch('app.services.invitations._email_settings', side_effect=get_settings)
        email_reader.start()
        self.addCleanup(email_reader.stop)

    def test_tls_submission_html_escaping_recipient_and_quit_failure(self):
        with patch.multiple(get_settings(), PUBLIC_FRONTEND_URL='https://maxbud.example.com', SMTP_HOST='smtp.example.com', SMTP_PORT=587, SMTP_FROM='maxbud@example.com', SMTP_USERNAME='synthetic', SMTP_PASSWORD='synthetic', SMTP_SECURITY='starttls'), patch('app.services.invitations.smtplib.SMTP') as transport:
            client = transport.return_value
            client.send_message.return_value = {}
            client.quit.side_effect = smtplib.SMTPServerDisconnected('quit only')
            message_id = delivery.send_invitation('member@example.com', household_name='<Our household>', inviter_name='Mathy', url='https://maxbud.example.com/invite#invite=synthetic')
            self.assertTrue(message_id)
            client.starttls.assert_called_once()
            client.login.assert_called_once_with('synthetic', 'synthetic')
            message = client.send_message.call_args.args[0]
            self.assertEqual(message['To'], 'member@example.com')
            self.assertEqual(client.send_message.call_args.kwargs['to_addrs'], ['member@example.com'])
            self.assertIn('&lt;Our household&gt;', message.get_body(preferencelist=('html',)).get_content())
            self.assertNotIn('localhost', message.as_string())
            client.send_message.return_value = {'member@example.com': (550, b'rejected')}
            with self.assertRaises(smtplib.SMTPRecipientsRefused):
                delivery.send_invitation('member@example.com', household_name='Household', inviter_name='Mathy', url='https://maxbud.example.com/invite#invite=synthetic')

    def test_gmail_app_password_formatting_and_authentication(self):
        with patch.multiple(get_settings(), PUBLIC_FRONTEND_URL='https://maxbud.example.com', SMTP_HOST='smtp.gmail.com', SMTP_PORT=465, SMTP_FROM='maxbud@example.com', SMTP_USERNAME='maxbud@example.com', SMTP_PASSWORD='abcd efgh ijkl mnop', SMTP_SECURITY='ssl'), patch('app.services.invitations.smtplib.SMTP_SSL') as transport:
            client = transport.return_value
            client.send_message.return_value = {}
            delivery.send_invitation('member@example.com', household_name='Household', inviter_name='Mathy', url='https://maxbud.example.com/invite#invite=synthetic')
            self.assertTrue(client.password == 'abcdefghijklmnop', 'Gmail formatting separators were not removed')
            client.auth.assert_called_once_with('LOGIN', client.auth_login, initial_response_ok=False)
            client.starttls.assert_not_called()
            with self.assertRaises(Exception):
                delivery.send_invitation('member@example.com', household_name='Household', inviter_name='Mathy', url='http://localhost:5173/invite#invite=synthetic')


class InvitationSettingsReloadTests(unittest.TestCase):
    def test_email_credentials_reload_without_clearing_application_settings(self):
        import tempfile
        from pathlib import Path
        from app.core.config import Settings
        cached = get_settings()
        with tempfile.TemporaryDirectory(prefix='maxbud-smtp-settings-') as directory:
            path = Path(directory) / '.env'
            prefix = 'SMTP_HOST=smtp.gmail.com\nSMTP_PORT=587\nSMTP_SECURITY=starttls\nSMTP_USERNAME=maxbud@example.com\nSMTP_FROM=maxbud@example.com\nPUBLIC_FRONTEND_URL=https://maxbud.example.com\n'
            def load():
                from dotenv import dotenv_values
                return Settings(_env_file=None, DB_USER='synthetic', DB_PASSWORD='synthetic', JWT_SECRET='x' * 48, **dotenv_values(path))
            with patch('app.services.invitations.Settings', side_effect=load):
                path.write_text(prefix + 'SMTP_PASSWORD=abcd efgh ijkl mnop\n')
                self.assertTrue(delivery.smtp_options()[4] == 'abcdefghijklmnop', 'First synthetic email credential was not loaded')
                path.write_text(prefix + 'SMTP_PASSWORD=qrst uvwx yzab cdef\n')
                self.assertTrue(delivery.smtp_options()[4] == 'qrstuvwxyzabcdef', 'Updated synthetic email credential was not loaded')
                self.assertTrue(get_settings() is cached)

    def test_invalid_email_settings_do_not_expose_validation_input(self):
        from fastapi import HTTPException
        from pydantic import ValidationError
        failure = ValidationError.from_exception_data('Email settings', [{'type': 'missing', 'loc': ('SMTP_HOST',), 'input': {'SMTP_PASSWORD': 'synthetic-sensitive-value'}}])
        with patch('app.services.invitations.Settings', side_effect=failure):
            with self.assertRaises(HTTPException) as caught:
                delivery._email_settings()
        self.assertEqual(caught.exception.status_code, 503)
        self.assertNotIn('synthetic-sensitive-value', str(caught.exception))
