import json

from tests.base import ApiDBTestCase

from zou.app.utils import auth, fields


class AuthTestCase(ApiDBTestCase):

    def setUp(self):
        super(AuthTestCase, self).setUp()

        self.generate_fixture_person()
        self.person.update({
            "password": auth.encrypt_password("secretpassword"),
            "role": "admin"
        })

        self.person_dict = self.person.serialize()
        self.credentials = {
            "email": self.person_dict["email"],
            "password": "secretpassword"
        }
        try:
            self.get("auth/logout")
        except AssertionError:
            pass

    def tearDown(self):
        try:
            self.get("auth/logout")
        except AssertionError:
            pass

    def get_auth_headers(self, tokens):
        return {"Authorization": "Bearer %s" % tokens.get("access_token", None)}

    def logout(self, tokens):
        headers = self.get_auth_headers(tokens)
        self.app.get("auth/logout", headers=headers)

    def assertIsAuthenticated(self, tokens):
        headers = self.get_auth_headers(tokens)
        response = self.app.get("auth/authenticated", headers=headers)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode("utf-8"))
        self.assertEquals(data["authenticated"], True)

    def assertIsNotAuthenticated(self, tokens, code=401):
        headers = self.get_auth_headers(tokens)
        response = self.app.get("auth/authenticated", headers=headers)
        self.assertEqual(response.status_code, code)

    def test_login(self):
        tokens = self.post("auth/login", self.credentials, 200)

        self.assertIsAuthenticated(tokens)
        self.logout(tokens)

    def test_unactive_login(self):
        self.person.update({"active": False})
        self.person.save()
        tokens = self.post("auth/login", self.credentials, 400)
        self.assertIsNotAuthenticated(tokens, 422)
        self.logout(tokens)

    def test_login_with_desktop_login(self):
        self.credentials = {
            "email": self.person_dict["desktop_login"],
            "password": "secretpassword"
        }
        tokens = self.post("auth/login", self.credentials, 200)

        self.assertIsAuthenticated(tokens)
        self.logout(tokens)

    def test_login_wrong_credentials(self):
        result = self.post("auth/login", {}, 400)
        self.assertIsNotAuthenticated(result, 422)

        credentials = {
            "email": self.person_dict["email"],
            "password": "wrongpassword"
        }
        result = self.post("auth/login", credentials, 400)
        self.assertFalse(result["login"])
        self.assertIsNotAuthenticated(result, 422)

    def test_logout(self):
        tokens = self.post("auth/login", self.credentials, 200)
        self.assertIsAuthenticated(tokens)
        self.logout(tokens)
        self.assertIsNotAuthenticated(tokens)

    def test_register(self):
        subscription_data = {
            "email": "alice@doe.com",
            "password": "123456",
            "password_2": "123456",
            "first_name": "Alice",
            "last_name": "Doe"
        }
        self.post("auth/register", subscription_data, 201)

        credentials = {
            "email": subscription_data["email"],
            "password": subscription_data["password"]
        }
        tokens = self.post("auth/login", credentials, 200)
        self.assertIsAuthenticated(tokens)
        self.logout(tokens)

    def test_register_bad_email(self):
        credentials = {
            "email": "alicedoecom",
            "password": "123456",
            "password_2": "123456",
            "first_name": "Alice",
            "last_name": "Doe"
        }
        self.post("auth/register", credentials, 400)

    def test_register_different_password(self):
        credentials = {
            "email": "alice@doe.com",
            "password": "123456",
            "password_2": "123457",
            "first_name": "Alice",
            "last_name": "Doe"
        }
        self.post("auth/register", credentials, 400)

    def test_register_password_too_short(self):
        credentials = {
            "email": "alice@doe.com",
            "password": "123",
            "password_2": "123",
            "first_name": "Alice",
            "last_name": "Doe"
        }
        self.post("auth/register", credentials, 400)

    def test_change_password(self):
        user_data = {
            "email": "alice@doe.com",
            "password": "123456",
            "password_2": "123456",
            "first_name": "Alice",
            "last_name": "Doe"
        }
        credentials = {
            "email": "alice@doe.com",
            "password": "123456",
        }
        self.post("auth/register", user_data, 201)
        tokens = self.post("auth/login", credentials, 200)
        self.assertIsAuthenticated(tokens)

        new_password = {
            "old_password": "123456",
            "password": "654321",
            "password_2": "654321"
        }
        credentials = {
            "email": "alice@doe.com",
            "password": "654321"
        }

        headers = self.get_auth_headers(tokens)
        response = self.app.post(
            "auth/change-password",
            data=new_password,
            headers=headers
        )
        self.assertEqual(response.status_code, 200)
        self.logout(tokens)

        tokens = self.post("auth/login", credentials, 200)
        self.assertIsAuthenticated(tokens)
        self.logout(tokens)

    def test_refresh_token(self):
        tokens = self.post("auth/login", self.credentials, 200)
        self.assertIsAuthenticated(tokens)

        headers = {
            "Authorization": "Bearer %s" % tokens.get("refresh_token", None)
        }
        result = self.app.get("auth/refresh-token", headers=headers)
        tokens_string = result.data.decode("utf-8")
        tokens = json.loads("%s" % tokens_string)
        self.assertIsAuthenticated(tokens)

        self.logout(tokens)
        self.assertIsNotAuthenticated(tokens)

    def test_person_list(self):
        self.assertIsNotAuthenticated({}, code=422)
        self.get("auth/person-list", 401)
        self.generate_fixture_user_cg_artist()
        self.log_in_cg_artist()
        persons = self.get("auth/person-list")
        self.assertEquals(len(persons), 3)
        self.log_out()

    def test_cookies_auth(self):
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1)" \
                     " AppleWebKit/537.36 (KHTML, like Gecko)" \
                     " Chrome/39.0.2171.95 Safari/537.36'}"
        headers = {
            "User-Agent": user_agent
        }

        response = self.app.get("data/persons")
        self.assertEquals(response.status_code, 401)
        response = self.app.post(
            "auth/login",
            data=fields.serialize_value(self.credentials),
            headers=headers
        )
        self.assertTrue("access_token" in response.headers["Set-Cookie"])
        response = self.app.get("data/persons")
        self.assertEquals(response.status_code, 200)
        response = self.app.get("auth/logout", headers=headers)