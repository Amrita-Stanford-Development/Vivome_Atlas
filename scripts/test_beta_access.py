import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import beta_access as ba
from build_pages_site import invited

# The vector web/tests/beta-gate.test.js checks against deploy/pages/beta-gate.js.
VECTOR = ("sha256$00112233445566778899aabbccddeeff$"
          "c61e9af5f5d5efcb41c31a256e2974cb74583fb334762c0c2b7f3f5a12d6703b")


class PasswordTests(unittest.TestCase):
    def test_the_hash_is_the_one_the_gate_checks(self):
        salt = bytes.fromhex("00112233445566778899aabbccddeeff")
        self.assertEqual(ba.password_hash("correct horse battery staple", salt), VECTOR)

    def test_each_hash_gets_its_own_salt(self):
        a, b = ba.password_hash("same password!"), ba.password_hash("same password!")
        self.assertNotEqual(a, b)
        self.assertRegex(a, r"^sha256\$[0-9a-f]{32}\$[0-9a-f]{64}$")

    def test_a_generated_password_is_long_and_easy_to_read_out(self):
        password = ba.generate_password()
        self.assertRegex(password, r"^[a-z2-9]{5}-[a-z2-9]{5}-[a-z2-9]{5}$")
        self.assertFalse(re.search(r"[01ilo]", password), "no characters that look alike")
        self.assertGreaterEqual(len(password), ba.MIN_LENGTH)

    def test_a_short_password_is_refused_before_anything_is_set(self):
        with mock.patch.object(ba, "put_secret") as put:
            with self.assertRaises(SystemExit):
                ba.set_password("short")
            put.assert_not_called()

    def test_a_new_password_sets_its_hash_and_a_new_session_key(self):
        with mock.patch.object(ba, "put_secret") as put:
            ba.set_password("a long enough password")
        names = [call.args[0] for call in put.call_args_list]
        self.assertEqual(names, ["BETA_PASSWORD_HASH", "BETA_SESSION_KEY"])
        self.assertRegex(put.call_args_list[1].args[1], r"^[0-9a-f]{64}$")


class EmailTests(unittest.TestCase):
    def test_add_and_remove_keep_one_line_each_and_the_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "beta" / "emails.txt"
            self.assertTrue(ba.add(path, "Owner@Example.org"))
            self.assertFalse(ba.add(path, "owner@example.org "), "already invited")
            self.assertTrue(ba.add(path, "friend@example.org"))
            self.assertEqual(invited(path), ["owner@example.org", "friend@example.org"])
            self.assertTrue(path.read_text().startswith("#"), "the file says what it is")
            self.assertTrue(ba.remove(path, "OWNER@example.org"))
            self.assertFalse(ba.remove(path, "nobody@example.org"))
            self.assertEqual(invited(path), ["friend@example.org"])
            self.assertNotIn(b"\r", path.read_bytes())

    def test_a_line_that_is_not_an_email_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                ba.add(Path(tmp) / "emails.txt", "not an email")


if __name__ == "__main__":
    unittest.main()
