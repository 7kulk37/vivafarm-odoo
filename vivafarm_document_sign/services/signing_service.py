"""Signing service — the ONLY migration-sensitive surface.

PoC (today, ฿0): FileKeyBackend signs with the PEM key in /etc/odoo/pki/.
Production (after Thai CA certificate): Pkcs11Backend signs via a USB token /
HSM using the SAME sign() interface — Odoo model code never changes.

The rest of the module (document records, hash chain, lock, audit, QR,
verification page) is backend-agnostic and does not change at migration.
"""
import base64
import hashlib
import logging
from datetime import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

_logger = logging.getLogger(__name__)

#: Path to the signer private key + certificate (PoC backend).
DEFAULT_PKI_DIR = '/etc/odoo/pki'

#: System parameter name for the signing backend provider.
BACKEND_PARAM = 'vivafarm_document_sign.backend'          # 'file' | 'pkcs11' (future)
PKI_DIR_PARAM = 'vivafarm_document_sign.pki_dir'          # default /etc/odoo/pki


def sha256_hex(data):
    """Return hex SHA-256 of bytes."""
    return hashlib.sha256(data).hexdigest()


class SigningBackend(object):
    """Abstract signing backend. Subclass and implement sign()."""

    def sign(self, data):
        raise NotImplementedError


class FileKeyBackend(SigningBackend):
    """PoC backend: RSA sign with a PEM private key on disk.

    Production swap = Pkcs11Backend with the same sign() contract.
    """

    def __init__(self, pki_dir):
        self.pki_dir = pki_dir

    def _key_path(self):
        return '%s/signer/signer.key' % self.pki_dir

    def _cert_path(self):
        return '%s/signer/signer.crt' % self.pki_dir

    def sign(self, data):
        with open(self._key_path(), 'rb') as f:
            key = serialization.load_pem_private_key(f.read(), password=None)
        sig = key.sign(data, padding.PKCS1v15(), hashes.SHA256())
        return sig

    def public_key_pem(self):
        """Public key (PEM) — used by verification, available to anyone."""
        with open(self._cert_path(), 'rb') as f:
            cert = x509.load_pem_x509_certificate(f.read())
        return cert.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def certificate_info(self):
        """Cert metadata dict — stored on the signed document for evidence."""
        with open(self._cert_path(), 'rb') as f:
            cert = x509.load_pem_x509_certificate(f.read())
        return {
            'subject': cert.subject.rfc4514_string(),
            'issuer': cert.issuer.rfc4514_string(),
            'serial': format(cert.serial_number, 'X'),
            'fingerprint': cert.fingerprint(hashes.SHA256()).hex(),
            'not_before': cert.not_valid_before_utc.isoformat(),
            'not_after': cert.not_valid_after_utc.isoformat(),
        }


class SigningService(object):
    """Facade used by Odoo models.

    - sha256_hex(pdf_bytes)       → hash
    - sign_pdf(pdf_bytes)         → (signature_b64, cert_info, signed_at)
    - verify(pdf_bytes, cert_pem) → True/False (detached RSA signature check)
    """

    def __init__(self, env):
        self.env = env
        backend_name = self.env['ir.config_parameter'].get_param(BACKEND_PARAM, 'file')
        pki_dir = self.env['ir.config_parameter'].get_param(PKI_DIR_PARAM, DEFAULT_PKI_DIR)
        if backend_name == 'pkcs11':
            # Production migration point — Pkcs11Backend imported lazily so the
            # PoC module never hard-depends on python-pkcs11.
            from .pkcs11_backend import Pkcs11Backend  # noqa: F401
            self.backend = Pkcs11Backend(pki_dir)
        else:
            self.backend = FileKeyBackend(pki_dir)

    def sign_pdf(self, pdf_bytes):
        """Sign PDF bytes. Returns (signature_b64, cert_info, signed_at_iso)."""
        signature = self.backend.sign(pdf_bytes)
        cert_info = self.backend.certificate_info()
        signed_at = datetime.utcnow().isoformat(timespec='seconds')
        return base64.b64encode(signature).decode(), cert_info, signed_at

    def verify_signature(self, pdf_bytes, signature_b64, cert_pem):
        """Verify detached RSA signature over pdf_bytes with the public key."""
        try:
            from cryptography.hazmat.primitives.serialization import load_pem_public_key
            pub = load_pem_public_key(cert_pem.encode())
            sig = base64.b64decode(signature_b64)
            pub.verify(sig, pdf_bytes, padding.PKCS1v15(), hashes.SHA256())
            return True
        except Exception:
            return False
