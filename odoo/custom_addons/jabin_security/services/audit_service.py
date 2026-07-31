from __future__ import annotations
import json
from typing import Any, Dict, Optional
from odoo import api, models
from odoo.addons.jabin_core import JsonHelper, JabinLogger
_logger = JabinLogger.get('security.audit_service')
_MAX_USER_AGENT = 256

class AuditService(models.AbstractModel):
    _name = 'jabin.audit.service'
    _description = 'JABIN Audit Service'

    @staticmethod
    def _extract_request_meta() -> Dict[str, Optional[str]]:
        meta: Dict[str, Optional[str]] = {'ip_address': None, 'user_agent': None, 'endpoint': None, 'request_id': None}
        try:
            from odoo.http import request
            httprequest = getattr(request, 'httprequest', None)
            if httprequest is not None:
                forwarded = httprequest.headers.get('X-Forwarded-For')
                if forwarded:
                    meta['ip_address'] = forwarded.split(',')[0].strip()
                else:
                    meta['ip_address'] = httprequest.remote_addr
                ua = httprequest.headers.get('User-Agent')
                if ua:
                    meta['user_agent'] = ua[:_MAX_USER_AGENT]
                meta['endpoint'] = httprequest.path
                meta['request_id'] = httprequest.headers.get('X-Request-ID') or httprequest.headers.get('X-Correlation-ID')
        except Exception:
            pass
        return meta

    @api.model
    def log(self, *, action: str, severity: str='info', user_id: Optional[int]=None, target_user_id: Optional[int]=None, ip_address: Optional[str]=None, user_agent: Optional[str]=None, endpoint: Optional[str]=None, request_id: Optional[str]=None, details: Optional[Dict[str, Any]]=None, summary: Optional[str]=None) -> Optional[int]:
        if not action:
            _logger.warning('Audit log called without an action; skipping.')
            return None
        req_meta = self._extract_request_meta()
        ip_address = ip_address or req_meta['ip_address']
        user_agent = user_agent or req_meta['user_agent']
        endpoint = endpoint or req_meta['endpoint']
        request_id = request_id or req_meta['request_id']
        details_text: Optional[str] = None
        if details is not None:
            try:
                details_text = JsonHelper.dumps(details)
            except Exception:
                try:
                    details_text = json.dumps(str(details))
                except Exception:
                    details_text = None
        valid_severities = ('info', 'warning', 'error', 'critical')
        if severity not in valid_severities:
            severity = 'info'
        vals: Dict[str, Any] = {'action': action, 'severity': severity, 'ip_address': ip_address, 'user_agent': user_agent, 'endpoint': endpoint, 'request_id': request_id, 'details': details_text, 'summary': summary}
        if user_id is not None:
            vals['user_id'] = user_id
        if target_user_id is not None:
            vals['target_user_id'] = target_user_id
        try:
            record = self.env['jabin.audit.log'].create(vals)
            _logger.debug('Audit entry written: action=%s severity=%s id=%s', action, severity, record.id)
            return record.id
        except Exception as exc:
            _logger.error('Failed to write audit log (action=%s): %s', action, exc)
            return None

    @api.model
    def log_login(self, user_id: int, success: bool=True, **extra: Any) -> Optional[int]:
        return self.log(action='auth.login', severity='info' if success else 'warning', user_id=user_id if success else None, target_user_id=user_id if not success else None, summary='Login successful' if success else 'Login failed', details={'success': success, **extra})

    @api.model
    def log_logout(self, user_id: int, **extra: Any) -> Optional[int]:
        return self.log(action='auth.logout', severity='info', user_id=user_id, summary='User logged out', details=extra or None)

    @api.model
    def log_token_refresh(self, user_id: int, **extra: Any) -> Optional[int]:
        return self.log(action='auth.token_refresh', severity='info', user_id=user_id, summary='Access token refreshed', details=extra or None)

    @api.model
    def log_unauthorized(self, user_id: Optional[int], action: str, **extra: Any) -> Optional[int]:
        return self.log(action=action, severity='warning', user_id=user_id, summary='Unauthorized access attempt blocked', details=extra or None)

    @api.model
    def query(self, *, action: Optional[str]=None, user_id: Optional[int]=None, target_user_id: Optional[int]=None, severity: Optional[str]=None, limit: int=100) -> list:
        domain = []
        if action:
            domain.append(('action', '=', action))
        if user_id:
            domain.append(('user_id', '=', user_id))
        if target_user_id:
            domain.append(('target_user_id', '=', target_user_id))
        if severity:
            domain.append(('severity', '=', severity))
        records = self.env['jabin.audit.log'].search(domain, order='create_date desc', limit=limit)
        return [r.to_dict() for r in records]