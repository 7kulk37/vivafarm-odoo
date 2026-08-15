#!/bin/bash
# pki_setup.sh — one-time test CA + signer certificate generation (PoC, ฿0)
#
# Creates /etc/odoo/pki/ with:
#   ca/ca.key       — test root CA private key (chmod 640, odoo:odoo)
#   ca/ca.crt       — test root CA certificate
#   signer/signer.key — signer private key (chmod 640, odoo:odoo)
#   signer/signer.crt — signer certificate (chained to test CA)
#   signer/signer.pub  — extracted public key (used by verification)
#
# Migration note: when a real Thai CA certificate is obtained, replace the
# signer.crt + signer.key with the CA-issued ones (or point the signing
# backend at the PKCS#11 token). The Odoo module reads cert metadata from
# these files at signing time — no module code change needed.
#
# TEST / NON-PRODUCTION — self-signed, NOT a legally trusted certificate.
set -euo pipefail

PKI_DIR=/etc/odoo/pki
CA_DAYS=3650
SIGNER_DAYS=365
ORG="${ORG:-Viva la Finca}"
COUNTRY="${COUNTRY:-TH}"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: run as root (sudo bash pki_setup.sh)" >&2
    exit 1
fi

echo "=== Creating $PKI_DIR ==="
mkdir -p "$PKI_DIR/ca" "$PKI_DIR/signer"
chown -R odoo:odoo "$PKI_DIR"
chmod 700 "$PKI_DIR" "$PKI_DIR/ca" "$PKI_DIR/signer"

# ── Root CA (self-signed) ──
if [ ! -f "$PKI_DIR/ca/ca.key" ]; then
    echo "=== Generating test Root CA ==="
    openssl req -x509 -newkey rsa:2048 \
        -keyout "$PKI_DIR/ca/ca.key" \
        -out "$PKI_DIR/ca/ca.crt" \
        -days "$CA_DAYS" -nodes \
        -subj "/CN=VivaFarm Test Root CA/O=$ORG/C=$COUNTRY"
else
    echo "=== CA key exists — skipping ==="
fi

# ── Signer certificate (issued by test CA) ──
if [ ! -f "$PKI_DIR/signer/signer.crt" ]; then
    echo "=== Generating signer key + CSR + certificate ==="
    openssl req -newkey rsa:2048 \
        -keyout "$PKI_DIR/signer/signer.key" \
        -out /tmp/signer.csr \
        -nodes \
        -subj "/CN=VivaFarm Test Signer/O=$ORG/C=$COUNTRY"
    openssl x509 -req \
        -in /tmp/signer.csr \
        -CA "$PKI_DIR/ca/ca.crt" \
        -CAkey "$PKI_DIR/ca/ca.key" \
        -CAcreateserial \
        -out "$PKI_DIR/signer/signer.crt" \
        -days "$SIGNER_DAYS"
    rm -f /tmp/signer.csr
else
    echo "=== Signer cert exists — skipping ==="
fi

# ── Extract public key for verification ──
openssl x509 -in "$PKI_DIR/signer/signer.crt" -pubkey -noout > "$PKI_DIR/signer/signer.pub"

# ── Hardening ──
chmod 640 "$PKI_DIR/ca/ca.key" "$PKI_DIR/signer/signer.key"
chmod 644 "$PKI_DIR/ca/ca.crt" "$PKI_DIR/signer/signer.crt" "$PKI_DIR/signer/signer.pub"
chown -R odoo:odoo "$PKI_DIR"

echo ""
echo "=== Certificate chain verification ==="
openssl verify -CAfile "$PKI_DIR/ca/ca.crt" "$PKI_DIR/signer/signer.crt"

echo ""
echo "=== Signer certificate ==="
openssl x509 -in "$PKI_DIR/signer/signer.crt" -noout -subject -issuer -fingerprint -sha256 -dates

echo ""
echo "=== TEST / NON-PRODUCTION — self-signed, not for legal use ==="
echo "DONE. Private keys at: $PKI_DIR/signer/signer.key (odoo:odoo, 640)"
