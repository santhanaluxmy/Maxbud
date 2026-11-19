"""Google login transport failures; no database or real OAuth requests."""
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from google.auth.exceptions import TransportError

from app.core.config import get_settings
from app.routers.auth import google_login
from app.schemas.auth import GoogleIn


class LoginTransportTests(unittest.TestCase):
    def test_google_certificate_request_has_short_timeout_and_safe_unavailable_error(self):
        transport = Mock(side_effect=TransportError('private transport diagnostic'))
        db = Mock()

        def verify(credential, request, client_id):
            return request('https://www.googleapis.com/oauth2/v1/certs', method='GET')

        with patch.object(get_settings(), 'GOOGLE_CLIENT_ID', 'synthetic-client'), \
             patch('app.routers.auth.Request', return_value=transport), \
             patch('app.routers.auth.id_token.verify_oauth2_token', side_effect=verify):
            with self.assertRaises(HTTPException) as error:
                google_login(GoogleIn(credential='synthetic-google-id-token'), db)
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(error.exception.detail, 'Google sign-in is temporarily unavailable. Please try again.')
        self.assertNotIn('private', error.exception.detail)
        self.assertEqual(transport.call_args.kwargs['timeout'], 10)
        self.assertEqual(db.mock_calls, [])

    def test_invalid_google_token_still_returns_unauthorized(self):
        db = Mock()
        with patch.object(get_settings(), 'GOOGLE_CLIENT_ID', 'synthetic-client'), \
             patch('app.routers.auth.id_token.verify_oauth2_token', side_effect=ValueError('invalid token')):
            with self.assertRaises(HTTPException) as error:
                google_login(GoogleIn(credential='synthetic-google-id-token'), db)
        self.assertEqual(error.exception.status_code, 401)
        self.assertEqual(db.mock_calls, [])
