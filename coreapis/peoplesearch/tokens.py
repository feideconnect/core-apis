import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


def crypt_token(uuid, key):
    backend = default_backend()
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=backend)
    encryptor = cipher.encryptor()
    msg = uuid.encode('UTF-8')
    msg = msg + b'\t' * (16 - len(msg) % 16)
    ct = base64.urlsafe_b64encode(encryptor.update(msg) + encryptor.finalize()).decode('ASCII')
    return ct


def decrypt_token(token, key):
    token = base64.urlsafe_b64decode(token)
    backend = default_backend()
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=backend)
    decryptor = cipher.decryptor()
    msg = decryptor.update(token) + decryptor.finalize()
    return msg.decode('UTF-8').strip()
