# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint
import werkzeug

from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)


class mygateController(http.Controller):
    @http.route(['/payment/mygate/return', '/payment/mygate/cancel', '/payment/mygate/error'], type='http', auth='public', csrf=False)
    def payu_return(self, **post):
        """ mygate."""
        _logger.info(
            'mygate: entering form_feedback with post data %s', pprint.pformat(post))
        return_url = '/shop/confirmation'
        if post.get('_RESULT') == '0':
            return_url = '/shop/confirmation'
        if post:
            request.env['payment.transaction'].sudo().form_feedback(post, 'mygate')
        return werkzeug.utils.redirect(return_url)

    @http.route(['/shop/confirmation'], type='http', auth="public", website=True)
    def payment_confirmation(self, **post):
        """ End of checkout process controller. Confirmation is basically seing
        the status of a sale.order. State at this point :

         - should not have any context / session info: clean them
         - take a sale.order id, because we request a sale.order and are not
           session dependant anymore
        """
        sale_order_id = request.session.get('sale_last_order_id')
        if sale_order_id:
            order = request.env['sale.order'].sudo().browse(sale_order_id)
            if not order or order.state != 'draft':
                request.website.sale_reset()
            return request.render("website_sale.confirmation", {'order': order})
        else:
            return request.redirect('/shop')
