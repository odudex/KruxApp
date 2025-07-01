import sys
from unittest import mock

from Crypto.Cipher import AES

if "ucryptolib" not in sys.modules:
    sys.modules["ucryptolib"] = mock.MagicMock(
        aes=AES.new,
        MODE_ECB=AES.MODE_ECB,
        MODE_CBC=AES.MODE_CBC,
        MODE_CTR=AES.MODE_CTR,
        MODE_GCM=AES.MODE_GCM
    )