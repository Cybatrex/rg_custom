# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import werkzeug

from odoo import http, _
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.addons.web.controllers.main import ensure_db, Home
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons.auth_signup.controllers.main import AuthSignupHome

_logger = logging.getLogger(__name__)


class AuthSignupHomeInuka(AuthSignupHome):

    @http.route('/web/reset_password', type='http', auth='public', website=True, sitemap=False)
    def web_auth_reset_password(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()

        if not qcontext.get('token') and not qcontext.get('reset_password_enabled'):
            raise werkzeug.exceptions.NotFound()

        if 'error' not in qcontext and request.httprequest.method == 'POST':
            try:
                if qcontext.get('token'):
                    self.do_signup(qcontext)
                    return super(AuthSignupHome, self).web_login(*args, **kw)
                else:
                    login = qcontext.get('login')
                    assert login, _("No login provided.")
                    _logger.info(
                        "Password reset attempt for <%s> by user <%s> from %s",
                        login, request.env.user.login, request.httprequest.remote_addr)
                    send_sms = send_mail = False
                    if kw.get('reset_via_sms'):
                        send_sms = True
                    if kw.get('reset_via_mail'):
                        send_mail = True
                    request.env['res.users'].sudo().with_context(reset_via_sms=send_sms, reset_via_mail=send_mail).reset_password(login)
                    if send_mail and not send_sms:
                        qcontext['message'] = _("An email has been sent with credentials to reset your password.")
                    if send_sms and not send_mail:
                        qcontext['message'] = _("An SMS has been sent with credentials to reset your password.")
                    if send_sms and send_mail:
                        qcontext['message'] = _("An email has been sent with credentials to reset your password.") + "\n" + _("An SMS has been sent with credentials to reset your password.")
            except SignupError:
                qcontext['error'] = _("Could not reset your password")
                _logger.exception('error when resetting password')
            except Exception as e:
                qcontext['error'] = str(e)

        response = request.render('auth_signup.reset_password', qcontext)
        response.headers['X-Frame-Options'] = 'DENY'
        return response
