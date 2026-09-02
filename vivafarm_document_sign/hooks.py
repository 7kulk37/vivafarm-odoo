"""post_init_hook — ensure a signing certificate exists.

A fresh deployment has no /etc/odoo/pki/: every sign flow crashes with
``FileNotFoundError: '/etc/odoo/pki/signer/signer.crt'`` and the DB keeps
NO signed evidence until someone runs data/pki_setup.sh by hand (found
2026-09-02 rebuilding audit_2027 from zero).

This hook runs once at module install/upgrade and generates the TEST CA +
signer certificate when the files are missing. Real-certificate rule:
if the signer cert ALREADY exists, this is a no-op — production swaps the
files (or points pki_dir at a PKCS#11 token) and nothing is overwritten.

Runs openssl via subprocess (the same commands as data/pki_setup.sh, which
stays authoritative for manual/production use).
"""
import logging
import os
import subprocess

_logger = logging.getLogger(__name__)

DEFAULT_PKI_DIR = '/etc/odoo/pki'
PKI_DIR_PARAM = 'vivafarm_document_sign.pki_dir'
CA_DAYS = 3650
SIGNER_DAYS = 365


def _ensure_certs(pki_dir):
    """Generate the test CA + signer cert when missing. Idempotent."""
    ca_dir = os.path.join(pki_dir, 'ca')
    signer_dir = os.path.join(pki_dir, 'signer')
    ca_key = os.path.join(ca_dir, 'ca.key')
    ca_crt = os.path.join(ca_dir, 'ca.crt')
    signer_key = os.path.join(signer_dir, 'signer.key')
    signer_crt = os.path.join(signer_dir, 'signer.crt')
    signer_pub = os.path.join(signer_dir, 'signer.pub')

    if os.path.exists(signer_crt):
        return False  # already provisioned (or production cert) — never touch

    org = os.environ.get('VIVA_PKI_ORG', 'Viva la Finca')
    country = os.environ.get('VIVA_PKI_COUNTRY', 'TH')
    subj_ca = f'/CN=VivaFarm Test Root CA/O={org}/C={country}'
    subj_signer = f'/CN=VivaFarm Test Signer/O={org}/C={country}'

    os.makedirs(ca_dir, exist_ok=True)
    os.makedirs(signer_dir, exist_ok=True)

    def run(args):
        subprocess.run(args, check=True, capture_output=True)

    if not os.path.exists(ca_key):
        run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048',
             '-keyout', ca_key, '-out', ca_crt,
             '-days', str(CA_DAYS), '-nodes', '-subj', subj_ca])
    if not os.path.exists(signer_crt):
        run(['openssl', 'req', '-newkey', 'rsa:2048',
             '-keyout', signer_key_path(signer_dir), '-out', '/tmp/signer.csr',
             '-nodes', '-subj', subj_signer])
        run(['openssl', 'x509', '-req',
             '-in', '/tmp/signer.csr',
             '-CA', ca_crt, '-CAkey', ca_key, '-CAcreateserial',
             '-out', signer_crt, '-days', str(SIGNER_DAYS)])
        if os.path.exists('/tmp/signer.csr'):
            os.unlink('/tmp/signer.csr')
    run(['openssl', 'x509', '-in', signer_crt, '-pubkey', '-noout',
         '-out', signer_pub])

    # Hardening: keys readable only by the odoo process owner.
    try:
        for f in (ca_key, signer_key_path(signer_dir)):
            os.chmod(f, 0o640)
        for f in (ca_crt, signer_crt, signer_pub):
            os.chmod(f, 0o644)
    except OSError:
        pass  # non-root dev environments — best effort
    return True


def signer_key_path(signer_dir):
    return os.path.join(signer_dir, 'signer.key')


def post_init_hook(env):
    """Module install/upgrade hook — provision the PoC test PKI if absent."""
    pki_dir = env['ir.config_parameter'].sudo().get_param(
        PKI_DIR_PARAM, DEFAULT_PKI_DIR)
    try:
        created = _ensure_certs(pki_dir)
        if created:
            _logger.info(
                'vivafarm_document_sign: generated TEST CA + signer '
                'certificate in %s (PoC — swap for a real Thai CA cert '
                'before production).', pki_dir)
    except (subprocess.CalledProcessError, OSError) as exc:
        # Signing stays broken but the module must not fail to install —
        # the admin can still run data/pki_setup.sh manually.
        _logger.error(
            'vivafarm_document_sign: could not provision test PKI in %s '
            '(%s). Run data/pki_setup.sh as root, then retry signing.',
            pki_dir, exc)