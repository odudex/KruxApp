"""
Copy-paste from key.py in bitcoin test_framework.
This is a fallback option if the library can't do ctypes bindings to secp256k1 library.
"""
import random
import hmac
import hashlib


def TaggedHash(tag, data):
    ss = hashlib.sha256(tag.encode("utf-8")).digest()
    ss += ss
    ss += data
    return hashlib.sha256(ss).digest()


def modinv(a, n):
    """Compute the modular inverse of a modulo n using the extended Euclidean
    Algorithm. See https://en.wikipedia.org/wiki/Extended_Euclidean_algorithm#Modular_integers.
    """
    # TODO: Change to pow(a, -1, n) available in Python 3.8
    t1, t2 = 0, 1
    r1, r2 = n, a
    while r2 != 0:
        q = r1 // r2
        t1, t2 = t2, t1 - q * t2
        r1, r2 = r2, r1 - q * r2
    if r1 > 1:
        return None
    if t1 < 0:
        t1 += n
    return t1


def xor_bytes(b0, b1):
    return bytes(x ^ y for (x, y) in zip(b0, b1))


def jacobi_symbol(n, k):
    """Compute the Jacobi symbol of n modulo k

    See http://en.wikipedia.org/wiki/Jacobi_symbol

    For our application k is always prime, so this is the same as the Legendre symbol.
    """
    if k <= 0 or k % 2 == 0:
        raise ValueError("jacobi symbol is only defined for positive odd k")
    n %= k
    t = 0
    while n != 0:
        while n & 1 == 0:
            n >>= 1
            r = k & 7
            t ^= r == 3 or r == 5
        n, k = k, n
        t ^= n & k & 3 == 3
        n = n % k
    if k == 1:
        return -1 if t else 1
    return 0


def modsqrt(a, p):
    """Compute the square root of a modulo p when p % 4 = 3.

    The Tonelli-Shanks algorithm can be used. See https://en.wikipedia.org/wiki/Tonelli-Shanks_algorithm

    Limiting this function to only work for p % 4 = 3 means we don't need to
    iterate through the loop. The highest n such that p - 1 = 2^n Q with Q odd
    is n = 1. Therefore Q = (p-1)/2 and sqrt = a^((Q+1)/2) = a^((p+1)/4)

    secp256k1's is defined over field of size 2**256 - 2**32 - 977, which is 3 mod 4.
    """
    if p % 4 != 3:
        raise NotImplementedError("modsqrt only implemented for p % 4 = 3")
    sqrt = pow(a, (p + 1) // 4, p)
    if pow(sqrt, 2, p) == a % p:
        return sqrt
    return None


class EllipticCurve:
    def __init__(self, p, a, b):
        """Initialize elliptic curve y^2 = x^3 + a*x + b over GF(p)."""
        self.p = p
        self.a = a % p
        self.b = b % p

    def affine(self, p1):
        """Convert a Jacobian point tuple p1 to affine form, or None if at infinity.

        An affine point is represented as the Jacobian (x, y, 1)"""
        x1, y1, z1 = p1
        if z1 == 0:
            return None
        inv = modinv(z1, self.p)
        inv_2 = (inv**2) % self.p
        inv_3 = (inv_2 * inv) % self.p
        return ((inv_2 * x1) % self.p, (inv_3 * y1) % self.p, 1)

    def has_even_y(self, p1):
        """Whether the point p1 has an even Y coordinate when expressed in affine coordinates."""
        return not (p1[2] == 0 or self.affine(p1)[1] & 1)

    def negate(self, p1):
        """Negate a Jacobian point tuple p1."""
        x1, y1, z1 = p1
        return (x1, (self.p - y1) % self.p, z1)

    def on_curve(self, p1):
        """Determine whether a Jacobian tuple p is on the curve (and not infinity)"""
        x1, y1, z1 = p1
        z2 = pow(z1, 2, self.p)
        z4 = pow(z2, 2, self.p)
        return (
            z1 != 0
            and (
                pow(x1, 3, self.p)
                + self.a * x1 * z4
                + self.b * z2 * z4
                - pow(y1, 2, self.p)
            )
            % self.p
            == 0
        )

    def is_x_coord(self, x):
        """Test whether x is a valid X coordinate on the curve."""
        x_3 = pow(x, 3, self.p)
        return jacobi_symbol(x_3 + self.a * x + self.b, self.p) != -1

    def lift_x(self, x):
        """Given an X coordinate on the curve, return a corresponding affine point for which the Y coordinate is even."""
        x_3 = pow(x, 3, self.p)
        v = x_3 + self.a * x + self.b
        y = modsqrt(v, self.p)
        if y is None:
            return None
        return (x, self.p - y if y & 1 else y, 1)

    def double(self, p1):
        """Double a Jacobian tuple p1

        See https://en.wikibooks.org/wiki/Cryptography/Prime_Curve/Jacobian_Coordinates - Point Doubling
        """
        x1, y1, z1 = p1
        if z1 == 0:
            return (0, 1, 0)
        y1_2 = (y1**2) % self.p
        y1_4 = (y1_2**2) % self.p
        x1_2 = (x1**2) % self.p
        s = (4 * x1 * y1_2) % self.p
        m = 3 * x1_2
        if self.a:
            m += self.a * pow(z1, 4, self.p)
        m = m % self.p
        x2 = (m**2 - 2 * s) % self.p
        y2 = (m * (s - x2) - 8 * y1_4) % self.p
        z2 = (2 * y1 * z1) % self.p
        return (x2, y2, z2)

    def add_mixed(self, p1, p2):
        """Add a Jacobian tuple p1 and an affine tuple p2

        See https://en.wikibooks.org/wiki/Cryptography/Prime_Curve/Jacobian_Coordinates - Point Addition (with affine point)
        """
        x1, y1, z1 = p1
        x2, y2, z2 = p2
        if z2 != 1:
            raise ValueError("p2 must be an affine point")
        # Adding to the point at infinity is a no-op
        if z1 == 0:
            return p2
        z1_2 = (z1**2) % self.p
        z1_3 = (z1_2 * z1) % self.p
        u2 = (x2 * z1_2) % self.p
        s2 = (y2 * z1_3) % self.p
        if x1 == u2:
            if y1 != s2:
                # p1 and p2 are inverses. Return the point at infinity.
                return (0, 1, 0)
            # p1 == p2. The formulas below fail when the two points are equal.
            return self.double(p1)
        h = u2 - x1
        r = s2 - y1
        h_2 = (h**2) % self.p
        h_3 = (h_2 * h) % self.p
        u1_h_2 = (x1 * h_2) % self.p
        x3 = (r**2 - h_3 - 2 * u1_h_2) % self.p
        y3 = (r * (u1_h_2 - x3) - y1 * h_3) % self.p
        z3 = (h * z1) % self.p
        return (x3, y3, z3)

    def add(self, p1, p2):
        """Add two Jacobian tuples p1 and p2

        See https://en.wikibooks.org/wiki/Cryptography/Prime_Curve/Jacobian_Coordinates - Point Addition
        """
        x1, y1, z1 = p1
        x2, y2, z2 = p2
        # Adding the point at infinity is a no-op
        if z1 == 0:
            return p2
        if z2 == 0:
            return p1
        # Adding an Affine to a Jacobian is more efficient since we save field multiplications and squarings when z = 1
        if z1 == 1:
            return self.add_mixed(p2, p1)
        if z2 == 1:
            return self.add_mixed(p1, p2)
        z1_2 = (z1**2) % self.p
        z1_3 = (z1_2 * z1) % self.p
        z2_2 = (z2**2) % self.p
        z2_3 = (z2_2 * z2) % self.p
        u1 = (x1 * z2_2) % self.p
        u2 = (x2 * z1_2) % self.p
        s1 = (y1 * z2_3) % self.p
        s2 = (y2 * z1_3) % self.p
        if u1 == u2:
            if s1 != s2:
                # p1 and p2 are inverses. Return the point at infinity.
                return (0, 1, 0)
            # p1 == p2. The formulas below fail when the two points are equal.
            return self.double(p1)
        h = u2 - u1
        r = s2 - s1
        h_2 = (h**2) % self.p
        h_3 = (h_2 * h) % self.p
        u1_h_2 = (u1 * h_2) % self.p
        x3 = (r**2 - h_3 - 2 * u1_h_2) % self.p
        y3 = (r * (u1_h_2 - x3) - s1 * h_3) % self.p
        z3 = (h * z1 * z2) % self.p
        return (x3, y3, z3)

    def mul(self, ps):
        """Compute a (multi) point multiplication

        ps is a list of (Jacobian tuple, scalar) pairs.
        """
        r = (0, 1, 0)
        for i in range(255, -1, -1):
            r = self.double(r)
            for p, n in ps:
                if (n >> i) & 1:
                    r = self.add(r, p)
        return r


SECP256K1_FIELD_SIZE = 2**256 - 2**32 - 977
SECP256K1 = EllipticCurve(SECP256K1_FIELD_SIZE, 0, 7)
SECP256K1_G = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
    1,
)
SECP256K1_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
SECP256K1_ORDER_HALF = SECP256K1_ORDER // 2


class ECPubKey:
    """A secp256k1 public key"""

    def __init__(self):
        """Construct an uninitialized public key"""
        self.valid = False

    def set(self, data):
        """Construct a public key from a serialization in compressed or uncompressed format"""
        if len(data) == 65 and data[0] == 0x04:
            p = (
                int.from_bytes(data[1:33], "big"),
                int.from_bytes(data[33:65], "big"),
                1,
            )
            self.valid = SECP256K1.on_curve(p)
            if self.valid:
                self.p = p
                self.compressed = False
        elif len(data) == 33 and (data[0] == 0x02 or data[0] == 0x03):
            x = int.from_bytes(data[1:33], "big")
            if SECP256K1.is_x_coord(x):
                p = SECP256K1.lift_x(x)
                # Make the Y coordinate odd if required (lift_x always produces
                # a point with an even Y coordinate).
                if data[0] & 1:
                    p = SECP256K1.negate(p)
                self.p = p
                self.valid = True
                self.compressed = True
            else:
                self.valid = False
        else:
            self.valid = False

    @property
    def is_compressed(self):
        return self.compressed

    @property
    def is_valid(self):
        return self.valid

    def get_bytes(self):
        if not self.valid:
            raise ValueError("Invalid public key")
        p = SECP256K1.affine(self.p)
        if p is None:
            return None
        if self.compressed:
            return bytes([0x02 + (p[1] & 1)]) + p[0].to_bytes(32, "big")
        else:
            return bytes([0x04]) + p[0].to_bytes(32, "big") + p[1].to_bytes(32, "big")

    def verify_ecdsa(self, sig, msg, low_s=True):
        """Verify a strictly DER-encoded ECDSA signature against this pubkey.

        See https://en.wikipedia.org/wiki/Elliptic_Curve_Digital_Signature_Algorithm for the
        ECDSA verifier algorithm"""
        if not self.valid:
            raise ValueError("Invalid public key")

        # Extract r and s from the DER formatted signature. Return false for
        # any DER encoding errors.
        if sig[1] + 2 != len(sig):
            return False
        if len(sig) < 4:
            return False
        if sig[0] != 0x30:
            return False
        if sig[2] != 0x02:
            return False
        rlen = sig[3]
        if len(sig) < 6 + rlen:
            return False
        if rlen < 1 or rlen > 33:
            return False
        if sig[4] >= 0x80:
            return False
        if rlen > 1 and (sig[4] == 0) and not (sig[5] & 0x80):
            return False
        r = int.from_bytes(sig[4 : 4 + rlen], "big")
        if sig[4 + rlen] != 0x02:
            return False
        slen = sig[5 + rlen]
        if slen < 1 or slen > 33:
            return False
        if len(sig) != 6 + rlen + slen:
            return False
        if sig[6 + rlen] >= 0x80:
            return False
        if slen > 1 and (sig[6 + rlen] == 0) and not (sig[7 + rlen] & 0x80):
            return False
        s = int.from_bytes(sig[6 + rlen : 6 + rlen + slen], "big")

        # Verify that r and s are within the group order
        if r < 1 or s < 1 or r >= SECP256K1_ORDER or s >= SECP256K1_ORDER:
            return False
        if low_s and s >= SECP256K1_ORDER_HALF:
            return False
        z = int.from_bytes(msg, "big")

        # Run verifier algorithm on r, s
        w = modinv(s, SECP256K1_ORDER)
        u1 = z * w % SECP256K1_ORDER
        u2 = r * w % SECP256K1_ORDER
        R = SECP256K1.affine(SECP256K1.mul([(SECP256K1_G, u1), (self.p, u2)]))
        if R is None or (R[0] % SECP256K1_ORDER) != r:
            return False
        return True


def generate_privkey():
    """Generate a valid random 32-byte private key."""
    return random.randrange(1, SECP256K1_ORDER).to_bytes(32, "big")


class ECKey:
    """A secp256k1 private key"""

    def __init__(self):
        self.valid = False

    def set(self, secret, compressed):
        """Construct a private key object with given 32-byte secret and compressed flag."""
        if len(secret) != 32:
            raise ValueError("Invalid secret key length")
        secret = int.from_bytes(secret, "big")
        self.valid = secret > 0 and secret < SECP256K1_ORDER
        if self.valid:
            self.secret = secret
            self.compressed = compressed

    def generate(self, compressed=True):
        """Generate a random private key (compressed or uncompressed)."""
        self.set(generate_privkey(), compressed)

    def get_bytes(self):
        """Retrieve the 32-byte representation of this key."""
        if not self.valid:
            raise ValueError("Invalid private key")
        return self.secret.to_bytes(32, "big")

    @property
    def is_valid(self):
        return self.valid

    @property
    def is_compressed(self):
        return self.compressed

    def get_pubkey(self):
        """Compute an ECPubKey object for this secret key."""
        if not self.valid:
            raise ValueError("Invalid private key")
        ret = ECPubKey()
        p = SECP256K1.mul([(SECP256K1_G, self.secret)])
        ret.p = p
        ret.valid = True
        ret.compressed = self.compressed
        return ret

    def sign_ecdsa(self, msg, nonce_function=None, extra_data=None, low_s=True):
        """Construct a DER-encoded ECDSA signature with this key.

        See https://en.wikipedia.org/wiki/Elliptic_Curve_Digital_Signature_Algorithm for the
        ECDSA signer algorithm."""
        if not self.valid:
            raise ValueError("Invalid private key")
        z = int.from_bytes(msg, "big")
        if nonce_function is None:
            nonce_function = deterministic_k
        k = nonce_function(self.secret, z, extra_data=extra_data)
        R = SECP256K1.affine(SECP256K1.mul([(SECP256K1_G, k)]))
        r = R[0] % SECP256K1_ORDER
        s = (modinv(k, SECP256K1_ORDER) * (z + self.secret * r)) % SECP256K1_ORDER
        if low_s and s > SECP256K1_ORDER_HALF:
            s = SECP256K1_ORDER - s
        # Represent in DER format. The byte representations of r and s have
        # length rounded up (255 bits becomes 32 bytes and 256 bits becomes 33
        # bytes).
        rb = r.to_bytes((r.bit_length() + 8) // 8, "big")
        sb = s.to_bytes((s.bit_length() + 8) // 8, "big")
        return (
            b"\x30"
            + bytes([4 + len(rb) + len(sb), 2, len(rb)])
            + rb
            + bytes([2, len(sb)])
            + sb
        )


def deterministic_k(secret, z, extra_data=None):
    # RFC6979, optimized for secp256k1
    k = b"\x00" * 32
    v = b"\x01" * 32
    if z > SECP256K1_ORDER:
        z -= SECP256K1_ORDER
    z_bytes = z.to_bytes(32, "big")
    secret_bytes = secret.to_bytes(32, "big")
    if extra_data is not None:
        z_bytes += extra_data
    k = hmac.new(k, v + b"\x00" + secret_bytes + z_bytes, "sha256").digest()
    v = hmac.new(k, v, "sha256").digest()
    k = hmac.new(k, v + b"\x01" + secret_bytes + z_bytes, "sha256").digest()
    v = hmac.new(k, v, "sha256").digest()
    while True:
        v = hmac.new(k, v, "sha256").digest()
        candidate = int.from_bytes(v, "big")
        if candidate >= 1 and candidate < SECP256K1_ORDER:
            return candidate
        k = hmac.new(k, v + b"\x00", "sha256").digest()
        v = hmac.new(k, v, "sha256").digest()


def compute_xonly_pubkey(key):
    """Compute an x-only (32 byte) public key from a (32 byte) private key.

    This also returns whether the resulting public key was negated.
    """

    if len(key) != 32:
        raise ValueError("Invalid private key length")
    x = int.from_bytes(key, "big")
    if x == 0 or x >= SECP256K1_ORDER:
        return (None, None)
    P = SECP256K1.affine(SECP256K1.mul([(SECP256K1_G, x)]))
    return (P[0].to_bytes(32, "big"), not SECP256K1.has_even_y(P))


def tweak_add_privkey(key, tweak):
    """Tweak a private key (after negating it if needed)."""

    if len(key) != 32:
        raise ValueError("Invalid private key length")
    if len(tweak) != 32:
        raise ValueError("Invalid tweak length")

    x = int.from_bytes(key, "big")
    if x == 0 or x >= SECP256K1_ORDER:
        return None
    if not SECP256K1.has_even_y(SECP256K1.mul([(SECP256K1_G, x)])):
        x = SECP256K1_ORDER - x
    t = int.from_bytes(tweak, "big")
    if t >= SECP256K1_ORDER:
        return None
    x = (x + t) % SECP256K1_ORDER
    if x == 0:
        return None
    return x.to_bytes(32, "big")


def tweak_add_pubkey(key, tweak):
    """Tweak a public key and return whether the result had to be negated."""

    if len(key) != 32:
        raise ValueError("Invalid public key length")
    if len(tweak) != 32:
        raise ValueError("Invalid tweak length")

    x_coord = int.from_bytes(key, "big")
    if x_coord >= SECP256K1_FIELD_SIZE:
        return None
    P = SECP256K1.lift_x(x_coord)
    if P is None:
        return None
    t = int.from_bytes(tweak, "big")
    if t >= SECP256K1_ORDER:
        return None
    Q = SECP256K1.affine(SECP256K1.mul([(SECP256K1_G, t), (P, 1)]))
    if Q is None:
        return None
    return (Q[0].to_bytes(32, "big"), not SECP256K1.has_even_y(Q))


def verify_schnorr(key, sig, msg):
    """Verify a Schnorr signature (see BIP 340).
    - key is a 32-byte xonly pubkey (computed using compute_xonly_pubkey).
    - sig is a 64-byte Schnorr signature
    - msg is a 32-byte message
    """
    if len(key) != 32:
        raise ValueError("Invalid public key length")
    if len(msg) != 32:
        raise ValueError("Invalid message length")
    if len(sig) != 64:
        raise ValueError("Invalid signature length")

    x_coord = int.from_bytes(key, "big")
    if x_coord == 0 or x_coord >= SECP256K1_FIELD_SIZE:
        return False
    P = SECP256K1.lift_x(x_coord)
    if P is None:
        return False
    r = int.from_bytes(sig[0:32], "big")
    if r >= SECP256K1_FIELD_SIZE:
        return False
    s = int.from_bytes(sig[32:64], "big")
    if s >= SECP256K1_ORDER:
        return False
    e = (
        int.from_bytes(TaggedHash("BIP0340/challenge", sig[0:32] + key + msg), "big")
        % SECP256K1_ORDER
    )
    R = SECP256K1.mul([(SECP256K1_G, s), (P, SECP256K1_ORDER - e)])
    if not SECP256K1.has_even_y(R):
        return False
    if ((r * R[2] * R[2]) % SECP256K1_FIELD_SIZE) != R[0]:
        return False
    return True


def sign_schnorr(key, msg, aux=None, flip_p=False, flip_r=False):
    """Create a Schnorr signature (see BIP 340)."""

    if len(key) != 32:
        raise ValueError("Invalid private key length")
    if len(msg) != 32:
        raise ValueError("Invalid message length")
    if aux is not None:
        if len(aux) != 32:
            raise ValueError("Invalid aux length")

    sec = int.from_bytes(key, "big")
    if sec == 0 or sec >= SECP256K1_ORDER:
        return None
    P = SECP256K1.affine(SECP256K1.mul([(SECP256K1_G, sec)]))
    if SECP256K1.has_even_y(P) == flip_p:
        sec = SECP256K1_ORDER - sec
    if aux is not None:
        t = (sec ^ int.from_bytes(TaggedHash("BIP0340/aux", aux), "big")).to_bytes(
            32, "big"
        )
    else:
        t = sec.to_bytes(32, "big")
    kp = (
        int.from_bytes(
            TaggedHash("BIP0340/nonce", t + P[0].to_bytes(32, "big") + msg), "big"
        )
        % SECP256K1_ORDER
    )
    if kp == 0:
        raise ValueError("k is zero")
    R = SECP256K1.affine(SECP256K1.mul([(SECP256K1_G, kp)]))
    k = kp if SECP256K1.has_even_y(R) != flip_r else SECP256K1_ORDER - kp
    e = (
        int.from_bytes(
            TaggedHash(
                "BIP0340/challenge",
                R[0].to_bytes(32, "big") + P[0].to_bytes(32, "big") + msg,
            ),
            "big",
        )
        % SECP256K1_ORDER
    )
    return R[0].to_bytes(32, "big") + ((k + e * sec) % SECP256K1_ORDER).to_bytes(
        32, "big"
    )
