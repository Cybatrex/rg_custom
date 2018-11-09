# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid

from itertools import groupby
from datetime import datetime, timedelta
from werkzeug.urls import url_encode

from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT

from odoo.tools.misc import formatLang

from odoo.addons import decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    _description = 'Sales Order'
    @api.onchange('bulk_master_id')
    def bulk_master_onchange(self):
        fiscal_position_obj = self.env['account.fiscal.position']
        if self.bulk_master_id.partner_shipping_id:
            self.partner_shipping_id = self.bulk_master_id.partner_shipping_id.id
            if self.fiscal_position_id:
                fiscal_position = fiscal_position_obj.search([("country_id", "=", self.bulk_master_id.partner_shipping_id.country_id.id)])
                for fiscal in fiscal_position:
                    self.fiscal_position_id = fiscal.id
    @api.model
    def create(self, vals):
        if vals.get('bulk_master_id'):
            bulk = self.env['bulk.master'].browse([vals.get('bulk_master_id')])
            if bulk.partner_shipping_id:
                vals['partner_shipping_id'] = bulk.partner_shipping_id.id
        res = super(SaleOrder, self).create(vals)
        return res

    @api.multi
    def write(self, vals):
        if vals.get('bulk_master_id'):
            bulk = self.env['bulk.master'].browse([vals.get('bulk_master_id')])
            vals['partner_shipping_id'] = bulk.partner_shipping_id.id
        res = super(SaleOrder, self).write(vals)
        return res

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    _description = 'Sales Order Line'

    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        super(SaleOrderLine, self).product_id_change()
        product = self.product_id.with_context(
            lang=self.order_id.partner_id.lang,
            partner=self.order_id.partner_id.id,
            quantity=self.product_uom_qty,
            date=self.order_id.date_order,
            pricelist=self.order_id.pricelist_id.id,
            uom=self.product_uom.id
        )

        if self.order_id.pricelist_id and self.order_id.partner_id:
            if self.order_id.fiscal_position_id:
                self.price_unit = self._get_display_price(product)
            else:
                self.price_unit = self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(product), product.taxes_id, self.tax_id, self.company_id)


    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        if not self.product_uom or not self.product_id:
            self.price_unit = 0.0
            return
        if self.order_id.pricelist_id and self.order_id.partner_id:
            product = self.product_id.with_context(
                lang=self.order_id.partner_id.lang,
                partner=self.order_id.partner_id.id,
                quantity=self.product_uom_qty,
                date=self.order_id.date_order,
                pricelist=self.order_id.pricelist_id.id,
                uom=self.product_uom.id,
                fiscal_position=self.env.context.get('fiscal_position')
            )
            if self.order_id.pricelist_id and self.order_id.partner_id:
                if self.order_id.fiscal_position_id:
                    self.price_unit = self._get_display_price(product)
                else:
                    self.price_unit = self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(product), product.taxes_id, self.tax_id, self.company_id)
