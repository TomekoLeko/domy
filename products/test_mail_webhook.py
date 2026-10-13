import json
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from domy.mail_webhook import post_mail_webhook


class _UrlopenResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@override_settings(MAIL_WEBHOOK='https://example.test/mail-webhook')
class PostMailWebhookRecipientTests(SimpleTestCase):
    def _post(self, receiver):
        captured = {}

        def fake_urlopen(req, timeout=10):
            captured['payload'] = json.loads(req.data.decode('utf-8'))
            captured['timeout'] = timeout
            return _UrlopenResponse()

        with patch('domy.mail_webhook.urlopen', side_effect=fake_urlopen):
            result = post_mail_webhook(
                receiver,
                'Temat',
                '<p>tresc</p>',
                context_label='test',
            )

        self.assertEqual(result['sent'], True)
        self.assertEqual(result['attempted'], True)
        return captured['payload']

    @override_settings(ENVIRONMENT='development')
    def test_development_sends_to_dev_recipient(self):
        with self.assertLogs('domy.mail_webhook', level='INFO') as logs:
            payload = self._post('buyer@example.com')

        self.assertEqual(payload['receiver'], 'ays@vp.pl')
        self.assertEqual(payload['subject'], 'Temat')
        self.assertEqual(payload['content'], '<p>tresc</p>')
        self.assertTrue(
            any(
                'buyer@example.com' in line and 'ays@vp.pl' in line
                for line in logs.output
            )
        )

    @override_settings(ENVIRONMENT='production')
    def test_production_keeps_caller_recipient(self):
        payload = self._post('buyer@example.com')

        self.assertEqual(payload['receiver'], 'buyer@example.com')
        self.assertEqual(payload['subject'], 'Temat')
        self.assertEqual(payload['content'], '<p>tresc</p>')

    @override_settings(ENVIRONMENT='staging')
    def test_non_development_keeps_caller_recipient(self):
        payload = self._post('buyer@example.com')

        self.assertEqual(payload['receiver'], 'buyer@example.com')
