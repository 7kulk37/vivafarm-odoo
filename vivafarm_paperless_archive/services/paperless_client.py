"""Paperless-ngx REST client — the ONLY place that talks HTTP to Paperless.

Pure Python (no Odoo imports) so it can be unit/integration tested
standalone and called from Odoo model code. Implements the subset of the
Paperless API the archive module needs, per the official docs (api.md):

  - POST /api/documents/post_document/   (multipart upload, returns task UUID)
  - GET  /api/tasks/?task_id=            (poll consumption; doc id on success)
  - GET  /api/documents/?custom_field_query=...   (search by custom field)
  - GET  /api/documents/{id}/download/   (fetch bytes back for verify)
  - GET  /api/custom_fields/ + POST      (ensure custom fields exist)

API versioning: every request sends `Accept: application/json; version=10`.
Paperless's own `checksum` field is MD5 and explicitly not security-grade —
integrity is proven by the caller's SHA-256 (see signed_document extension).
"""
import hashlib
import json
import time

import requests

# Paperless API versions. Staging runs 2.20.15 which serves API v9 and
# REJECTS an explicit version=10 Accept header ("Invalid version") — so the
# client does NOT pin a version by default; it omits the header and lets the
# server serve its default, then records the server's X-Api-Version header.
SUPPORTED_API_VERSIONS = (9, 10)


class PaperlessError(Exception):
    """Base error — network, HTTP, or consumption failure."""


class PaperlessClient:
    def __init__(self, base_url, token, timeout=15, api_version=None):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.timeout = timeout
        self.api_version = api_version  # None = server default
        self.server_api_version = None  # set after first response
        self._session = requests.Session()
        headers = {'Authorization': 'Token %s' % token}
        if api_version:
            headers['Accept'] = 'application/json; version=%d' % api_version
        self._session.headers.update(headers)

    def _record_server_version(self, resp):
        v = resp.headers.get('X-Api-Version')
        if v and v != self.server_api_version:
            self.server_api_version = v

    # ── low-level helpers ──
    def _get(self, path, params=None):
        try:
            resp = self._session.get(self.base_url + path, params=params,
                                     timeout=self.timeout)
        except requests.RequestException as e:
            raise PaperlessError('GET %s failed: %s' % (path, e))
        self._record_server_version(resp)
        if resp.status_code >= 400:
            raise PaperlessError('GET %s -> HTTP %s: %s'
                                 % (path, resp.status_code,
                                    resp.text[:300]))
        return resp

    def _post(self, path, data=None, files=None):
        try:
            resp = self._session.post(self.base_url + path, data=data,
                                      files=files, timeout=self.timeout)
        except requests.RequestException as e:
            raise PaperlessError('POST %s failed: %s' % (path, e))
        self._record_server_version(resp)
        if resp.status_code >= 400:
            raise PaperlessError('POST %s -> HTTP %s: %s'
                                 % (path, resp.status_code,
                                    resp.text[:300]))
        return resp

    # ── custom fields ──
    def ensure_custom_field(self, name, data_type):
        """Return the id of a custom field, creating it if missing.

        data_type is one of the official types (text, integer, url, ...).
        Paperless rejects duplicate field names; data_type is immutable.
        """
        resp = self._get('/api/custom_fields/')
        for f in resp.json().get('results', []):
            if f.get('name') == name:
                return f['id']
        resp = self._post('/api/custom_fields/',
                          data={'name': name, 'data_type': data_type})
        return resp.json()['id']

    # ── search ──
    def search_by_custom_field(self, field_name, value):
        """Return list of document ids whose custom field equals value."""
        import json
        q = json.dumps([field_name, 'exact', value])
        resp = self._get('/api/documents/',
                         params={'custom_field_query': q, 'page_size': 100})
        return [d['id'] for d in resp.json().get('results', [])]

    # ── upload ──
    def upload_pdf(self, title, pdf_bytes, custom_fields=None,
                   document_type_id=None, tag_ids=None, created=None):
        """Upload a PDF; returns (document_id, task_id) after consumption.

        custom_fields: {field_id: value} per official post_document API.
        created: ISO date string (API v9+ treats created as a date).
        Raises PaperlessError on network/HTTP failure OR if consumption
        fails/times out (waits up to ~60s for the OCR pipeline).
        """
        files = {'document': ('document.pdf', pdf_bytes,
                              'application/pdf')}
        data = {'title': title}
        if custom_fields:
            # MUST be a JSON string — requests form-encodes a raw dict into
            # a Python repr ('{1: 2}') and Paperless silently drops it.
            # Verified on v9 (2026-08-27): json.dumps works, raw dict doesn't.
            data['custom_fields'] = json.dumps(custom_fields)
        if document_type_id:
            data['document_type'] = document_type_id
        for tag_id in tag_ids or []:
            data.setdefault('tags', []).append(tag_id)
        if created:
            data['created'] = created
        resp = self._post('/api/documents/post_document/', data=data,
                          files=files)
        # Official API: returns the consumption task UUID as the data
        # (a bare string). Some versions wrap it: {"task_id": "..."}.
        body = resp.json()
        if isinstance(body, dict):
            task_id = body.get('task_id') or body.get('id')
        else:
            task_id = body
        if not task_id:
            raise PaperlessError('upload response missing task_id: %s'
                                 % resp.text[:200])
        return self._wait_for_task(task_id)

    def _wait_for_task(self, task_id, max_wait=60):
        deadline = time.time() + max_wait
        last = ''
        while time.time() < deadline:
            resp = self._get('/api/tasks/', params={'task_id': task_id})
            data = resp.json()
            # v10 paginates ({'results': [...]}); v9 returns a bare list.
            rows = data.get('results') if isinstance(data, dict) else data
            if not rows:
                raise PaperlessError('task %s not found' % task_id)
            task = rows[0]
            status = task.get('status')
            last = task.get('result') or ''
            if status == 'SUCCESS':
                # v9 task shape: related_document = "<doc id>" (string).
                # v10 adds document_id / existing_document_id.
                doc_id = task.get('related_document') or task.get('document_id') \
                    or task.get('existing_document_id')
                try:
                    doc_id = int(doc_id)
                except (TypeError, ValueError):
                    doc_id = None
                return doc_id, task_id
            if status in ('FAILURE', 'REVOKED'):
                raise PaperlessError('consumption %s: %s'
                                     % (status, last[:300]))
            time.sleep(1.5)
        raise PaperlessError('consumption timed out after %ss: %s'
                             % (max_wait, last[:200]))

    # ── download ──
    def download_document(self, doc_id):
        """Return the raw archived bytes for a document."""
        resp = self._get('/api/documents/%d/download/' % doc_id)
        return resp.content

    def sha256(self, data):
        return hashlib.sha256(data).hexdigest()
