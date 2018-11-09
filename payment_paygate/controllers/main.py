from odoo import http
import logging

_logger = logging.getLogger(__name__)


class payGateController(http.Controller):
    _notify_url = '/payment/paygate/notify'
    _return_url = '/payment/paygate/return_url'

    @http.route('/payment/paygate/notify',
        type='http', auth='none', methods=['POST'], csrf=False)
    def paygate_notify(self, **post):
        import pdb; pdb.set_trace()
        return ''

    @http.route('/payment/paygate/return_url', type='http', auth="none", methods=['POST'], csrf=False)
    def paygate_return(self, **post):
        import pdb; pdb.set_trace()