"""Unit tests for the signing service (run in odoo shell on staging).

Tests the core crypto contract WITHOUT any Odoo model dependencies:
  1. sha256_hex is stable
  2. sign_pdf returns signature + cert info
  3. verify_signature accepts the original bytes
  4. verify_signature REJECTS tampered bytes (the money test)
  5. cert info fields are populated (migration-readiness: generic names)
"""
import sys
sys.path.insert(0, '/opt/odoo-custom-addons/vivafarm_document_sign/services')

from signing_service import SigningService, FileKeyBackend, sha256_hex

PASS = 0
FAIL = 0


def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('  ✅ %s %s' % (name, detail))
    else:
        FAIL += 1
        print('  ❌ %s %s' % (name, detail))


# ── Direct backend tests (no env needed) ──
backend = FileKeyBackend('/etc/odoo/pki')
pdf_bytes = b'%PDF-1.4 fake invoice bytes INV/2026/00058 original'
tampered = pdf_bytes.replace(b'00058', b'00059')

h1 = sha256_hex(pdf_bytes)
h2 = sha256_hex(pdf_bytes)
check('sha256 stable', h1 == h2 and len(h1) == 64, h1[:16])

sig = backend.sign(pdf_bytes)
check('RSA signature 256 bytes', len(sig) == 256, 'len=%d' % len(sig))

pub_pem = backend.public_key_pem()
check('public key PEM extractable', pub_pem.startswith('-----BEGIN PUBLIC KEY-----'))

# verify with cryptography directly (independent of service)
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

pub = serialization.load_pem_public_key(pub_pem.encode())
try:
    pub.verify(sig, pdf_bytes, padding.PKCS1v15(), hashes.SHA256())
    check('verify original (direct)', True)
except Exception:
    check('verify original (direct)', False)

try:
    pub.verify(sig, tampered, padding.PKCS1v15(), hashes.SHA256())
    check('tamper detected (direct)', False)
except Exception:
    check('tamper detected (direct)', True)

cert = backend.certificate_info()
check('cert subject', 'VivaFarm Test Signer' in cert['subject'], cert['subject'])
check('cert issuer', 'VivaFarm Test Root CA' in cert['issuer'], cert['issuer'])
check('cert serial hex', len(cert['serial']) > 0)
check('cert fingerprint sha256', len(cert['fingerprint']) == 64, cert['fingerprint'][:16])
check('cert validity dates', cert['not_before'] < cert['not_after'])

# ── Service-level tests (needs an env for config params — use a fake) ──
class FakeEnv(object):
    def __getitem__(self, key):
        return self

    def get_param(self, key, default=None):
        return default

    class config:
        @staticmethod
        def get_param(key, default=None):
            # no system parameters set → defaults
            return default


service = SigningService(FakeEnv())
sig_b64, cert_info, signed_at = service.sign_pdf(pdf_bytes)
check('service sign returns b64', isinstance(sig_b64, str) and len(sig_b64) > 100)
check('service cert info populated', 'CN=' in cert_info.get('subject', ''), cert_info.get('subject', ''))
check('service signed_at ISO', 'T' in signed_at)

ok = service.verify_signature(pdf_bytes, sig_b64, pub_pem)
check('service verify original', ok is True)

ok = service.verify_signature(tampered, sig_b64, pub_pem)
check('service verify tampered REJECTED', ok is False)

# bad signature / bad key
ok = service.verify_signature(pdf_bytes, 'AAAA', pub_pem)
check('garbage signature rejected', ok is False)

print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
