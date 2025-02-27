from .base import BaseTest
from posthog.models import User

class TestUser(BaseTest):
    TESTS_API = True
    def test_redirect_to_site(self):
        self.team.app_urls = ['http://somewebsite.com']
        self.team.save()
        response = self.client.get('/api/user/redirect_to_site/?actionId=1')
        self.assertIn('http://somewebsite.com', response.url)

    def test_create_user_when_restricted(self):
        with self.settings(RESTRICT_SIGNUPS='posthog.com,uk.posthog.com'):
            with self.assertRaisesMessage(ValueError, "Can't sign up with this email"):
                User.objects.create_user(email='tim@gmail.com')

            user = User.objects.create_user(email='tim@uk.posthog.com')
            self.assertEqual(user.email, 'tim@uk.posthog.com')

    def test_create_user_with_distinct_id(self):
        with self.settings(TEST=False):
            user = User.objects.create_user(email='tim@gmail.com')
        self.assertNotEqual(user.distinct_id, '')
        self.assertNotEqual(user.distinct_id, None)


class TestUserChangePassword(BaseTest):
    TESTS_API = True
    ENDPOINT:str = '/api/user/change_password/'

    def send_request(self, payload):
        return self.client.patch(self.ENDPOINT, payload, content_type='application/json')

    def test_change_password_no_data(self):
        response = self.send_request({})
        self.assertEqual(response.status_code, 400)

    def test_change_password_invalid_old_password(self):
        response = self.send_request({
            'oldPassword': '12345',
            'newPassword': '12345'
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Incorrect old password')

    def test_change_password_invalid_new_password(self):
        response = self.send_request({
            'oldPassword': self.TESTS_PASSWORD,
            'newPassword': '123451230'
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'This password is entirely numeric.')

    def test_change_password_success(self):
        response = self.send_request({
            'oldPassword': self.TESTS_PASSWORD,
            'newPassword': 'prettyhardpassword123456'
        })
        self.assertEqual(response.status_code, 200)

class TestLoginViews(BaseTest):
    def test_redirect_to_setup_admin_when_no_users(self):
        User.objects.all().delete()
        response = self.client.get('/', follow=True)
        self.assertRedirects(response, '/setup_admin')
