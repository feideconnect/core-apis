import unittest
import os
from coreapis.peoplesearch import tokens


class TestTokens(unittest.TestCase):
    def test_decryptable(self):
        key = os.urandom(32)
        msg = 'My secret'
        token = tokens.crypt_token(msg, key)
        assert token != msg
        msg2 = tokens.decrypt_token(token, key)
        assert msg2 == msg

    def test_unpredictable(self):
        key = os.urandom(32)
        msg = 'My secret'
        token = tokens.crypt_token(msg, key)
        token2 = tokens.crypt_token(msg, key)
        assert token != token2
