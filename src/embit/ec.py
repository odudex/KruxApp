from . import base58
from . import hashes
from .misc import secp256k1
from .networks import NETWORKS
from .base import EmbitBase, EmbitError, EmbitKey
from binascii import hexlify, unhexlify


class ECError(EmbitError):
    pass


class Signature(EmbitBase):
    def __init__(self, sig):
        self._sig = sig

    def write_to(self, stream) -> int:
        return stream.write(secp256k1.ecdsa_signature_serialize_der(self._sig))

    @classmethod
    def read_from(cls, stream):
        der = stream.read(2)
        der += stream.read(der[1])
        return cls(secp256k1.ecdsa_signature_parse_der(der))


class SchnorrSig(EmbitBase):
    def __init__(self, sig):
        if len(sig) != 64:
            raise ECError("Invalid schnorr signature")
        self._sig = sig

    def write_to(self, stream) -> int:
        return stream.write(self._sig)

    @classmethod
    def read_from(cls, stream):
        return cls(stream.read(64))


class PublicKey(EmbitKey):
    def __init__(self, point: bytes, compressed: bool = True):
        self._point = point
        self.compressed = compressed

    @classmethod
    def read_from(cls, stream):
        b = stream.read(1)
        if b not in [b"\x02", b"\x03", b"\x04"]:
            raise ECError("Invalid public key")
        if b == b"\x04":
            b += stream.read(64)
        else:
            b += stream.read(32)
        try:
            point = secp256k1.ec_pubkey_parse(b)
        except Exception as e:
            raise ECError(str(e))
        compressed = b[0] != 0x04
        return cls(point, compressed)

    def sec(self) -> bytes:
        """Sec representation of the key"""
        flag = secp256k1.EC_COMPRESSED if self.compressed else secp256k1.EC_UNCOMPRESSED
        return secp256k1.ec_pubkey_serialize(self._point, flag)

    def xonly(self) -> bytes:
        return self.sec()[1:33]

    def taproot_tweak(self, h=b""):
        """Returns a tweaked public key"""
        x = self.xonly()
        tweak = hashes.tagged_hash("TapTweak", x + h)
        if not secp256k1.ec_seckey_verify(tweak):
            raise EmbitError("Tweak is too large")
        point = secp256k1.ec_pubkey_parse(b"\x02" + x)
        pub = secp256k1.ec_pubkey_add(point, tweak)
        sec = secp256k1.ec_pubkey_serialize(pub)
        return PublicKey.from_xonly(sec[1:33])

    def write_to(self, stream) -> int:
        return stream.write(self.sec())

    def serialize(self) -> bytes:
        return self.sec()

    def verify(self, sig, msg_hash) -> bool:
        return bool(secp256k1.ecdsa_verify(sig._sig, msg_hash, self._point))

    def _xonly(self):
        """Returns internal representation of the xonly-pubkey (64 bytes)"""
        pub, _ = secp256k1.xonly_pubkey_from_pubkey(self._point)
        return pub

    @classmethod
    def from_xonly(cls, data: bytes):
        if len(data) != 32:
            raise ECError("Invalid xonly pubkey")
        return cls.parse(b"\x02" + data)

    def schnorr_verify(self, sig, msg_hash) -> bool:
        return bool(secp256k1.schnorrsig_verify(sig._sig, msg_hash, self._xonly()))

    @classmethod
    def from_string(cls, s):
        return cls.parse(unhexlify(s))

    @property
    def is_private(self) -> bool:
        return False

    def to_string(self):
        return hexlify(self.sec()).decode()

    def __lt__(self, other):
        # for lexagraphic ordering
        return self.sec() < other.sec()

    def __gt__(self, other):
        # for lexagraphic ordering
        return self.sec() > other.sec()

    def __eq__(self, other):
        return self.sec() == other.sec()

    def __hash__(self):
        return hash(self._point)


class PrivateKey(EmbitKey):
    def __init__(self, secret, compressed: bool = True, network=NETWORKS["main"]):
        """Creates a private key from 32-byte array"""
        if len(secret) != 32:
            raise ECError("Secret should be 32-byte array")
        if not secp256k1.ec_seckey_verify(secret):
            raise ECError("Secret is not valid (larger then N?)")
        self.compressed = compressed
        self._secret = secret
        self.network = network

    def wif(self, network=None) -> str:
        """Export private key as Wallet Import Format string.
        Prefix 0x80 is used for mainnet, 0xEF for testnet.
        This class doesn't store this information though.
        """
        if network is None:
            network = self.network
        prefix = network["wif"]
        b = prefix + self._secret
        if self.compressed:
            b += bytes([0x01])
        return base58.encode_check(b)

    @property
    def secret(self):
        return self._secret

    def sec(self) -> bytes:
        """Sec representation of the corresponding public key"""
        return self.get_public_key().sec()

    def xonly(self) -> bytes:
        return self.sec()[1:]

    def taproot_tweak(self, h=b""):
        """Returns a tweaked private key"""
        sec = self.sec()
        negate = sec[0] != 0x02
        x = sec[1:33]
        tweak = hashes.tagged_hash("TapTweak", x + h)
        if not secp256k1.ec_seckey_verify(tweak):
            raise EmbitError("Tweak is too large")
        if negate:
            secret = secp256k1.ec_privkey_negate(self._secret)
        else:
            secret = self._secret
        res = secp256k1.ec_privkey_add(secret, tweak)
        pk = PrivateKey(res)
        if pk.sec()[0] == 0x03:
            pk = PrivateKey(secp256k1.ec_privkey_negate(res))
        return pk

    @classmethod
    def from_wif(cls, s):
        """Import private key from Wallet Import Format string."""
        b = base58.decode_check(s)
        prefix = b[:1]
        network = None
        for net in NETWORKS:
            if NETWORKS[net]["wif"] == prefix:
                network = NETWORKS[net]
        secret = b[1:33]
        compressed = False
        if len(b) not in [33, 34]:
            raise ECError("Wrong WIF length")
        if len(b) == 34:
            if b[-1] == 0x01:
                compressed = True
            else:
                raise ECError("Wrong WIF compressed flag")
        return cls(secret, compressed, network)

    # to unify API
    def to_base58(self, network=None) -> str:
        return self.wif(network)

    @classmethod
    def from_base58(cls, s):
        return cls.from_wif(s)

    def get_public_key(self) -> PublicKey:
        return PublicKey(secp256k1.ec_pubkey_create(self._secret), self.compressed)

    def to_public(self) -> PublicKey:
        """Alias to get_public_key for API consistency"""
        return self.get_public_key()

    def sign(self, msg_hash, grind=True) -> Signature:
        sig = Signature(secp256k1.ecdsa_sign(msg_hash, self._secret))
        if grind:
            counter = 1
            while len(sig.serialize()) > 70:
                sig = Signature(
                    secp256k1.ecdsa_sign(
                        msg_hash, self._secret, None, counter.to_bytes(32, "little")
                    )
                )
                counter += 1
                # just in case we get in infinite loop for some reason
                if counter > 200:
                    break
        return sig

    def schnorr_sign(self, msg_hash) -> SchnorrSig:
        return SchnorrSig(secp256k1.schnorrsig_sign(msg_hash, self._secret))

    def verify(self, sig, msg_hash) -> bool:
        return self.get_public_key().verify(sig, msg_hash)

    def schnorr_verify(self, sig, msg_hash) -> bool:
        return self.get_public_key().schnorr_verify(sig, msg_hash)

    def write_to(self, stream) -> int:
        # return a copy of the secret
        return stream.write(self._secret)

    def ecdh(self, public_key: PublicKey, hashfn=None, data=None) -> bytes:
        pubkey_point = secp256k1.ec_pubkey_parse(public_key.sec())
        return secp256k1.ecdh(pubkey_point, self._secret, hashfn, data)

    @classmethod
    def read_from(cls, stream):
        # just to unify the API
        return cls(stream.read(32))

    @property
    def is_private(self) -> bool:
        return True


# Nothing up my sleeve point for no-internal-key taproot
# see https://github.com/bitcoin/bips/blob/master/bip-0341.mediawiki#constructing-and-spending-taproot-outputs
NUMS_PUBKEY = PublicKey.from_string(
    "0250929b74c1a04954b78b4b6035e97a5e078a5a0f28ec96d547bfee9ace803ac0"
)
