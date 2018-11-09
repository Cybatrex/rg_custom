from openerp import fields, models, api
import openerp.addons.decimal_precision as dp
from odoo.addons import decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)

class account_invoice(models.Model):

    _inherit = 'account.invoice'

    pricelist_id = fields.Many2one("product.pricelist", "Sale Pricelist")
    printed = fields.Boolean("Printed")
    nothing = fields.Char("Nothing")
    region = fields.Char("Region", related="partner_id.region")

    @api.onchange('partner_shipping_id')
    def get_partner_shipping_id(self):
        res_partner_obj = self.env['res.partner']
        ids = []
        parent_ids = res_partner_obj.search([('parent_id', '=', self.partner_id.id)])
        bulk_ids = res_partner_obj.search([('name', 'like', 'bulk')])
        bulk_ids1 = res_partner_obj.search([('name', 'like', 'Bulk')])
        bulk_ids2 = res_partner_obj.search([('name', 'like', 'BULK')])
        for line in parent_ids:
            ids.append(line.id)
        for line in bulk_ids:
            ids.append(line.id)
        for line in bulk_ids1:
            ids.append(line.id)
        for line in bulk_ids2:
            ids.append(line.id)

        return {'domain':{'partner_shipping_id': [('id', 'in', ids)]}}


    @api.onchange('partner_id')
    def pricelist_change(self):
        pricelist_obj = self.env['product.pricelist']
        if self.partner_id.status in ['new', 'candidate']:
            pricelist = pricelist_obj.search([('name', '=', 'Namibia New')])
            if self.partner_id.country_id.name != "Namibia":
                pricelist = pricelist_obj.search([('name', '=', 'RSA New')])
            if pricelist:
                self.pricelist_id = pricelist.id
        else:
            pricelist = pricelist_obj.search([('name', '=', 'Namibia Established')])
            if self.partner_id.country_id.name != "Namibia":
                pricelist = pricelist_obj.search([('name', '=', 'RSA Established')])
            if pricelist:
                self.pricelist_id = pricelist.id

    def get_address(self, invoice_id):
        if invoice_id.partner_shipping_id:
            return invoice_id.partner_shipping_id
        return invoice_id.partner_id

    @api.onchange('team_id')
    def channel_change(self):
        #"If Sales Team = ""Point of Sales"" then Channel = ""Front Office""
        #If Sales Team = ""Sales"" then Channel = ""Admin"""
        if self.team_id:
            if self.team_id.name == "Sales":
                self.channel = "admin"
            if self.team_id.name == "Point of Sale":
                self.channel = "front"

    @api.model
    def create(self, vals):
        if vals.get("origin"):
            if "SO" in vals.get("origin"):
                sale_orders = self.env["sale.order"].search([("name", "=", vals.get("origin"))])
                for order in sale_orders:
                    if order.team_id:
                        if order.team_id.name == "Sales":
                            vals["channel"] = "admin"
                        if order.team_id.name == "Point of Sale":
                            vals["channel"] = "front"
                    vals["pricelist_id"] = order.pricelist_id.id
        return super(account_invoice, self).create(vals)


class account_invoice_line(models.Model):

    _inherit = 'account.invoice.line'

    def _get_real_price_currency(self, product, rule_id, qty, uom, pricelist_id):
        """Retrieve the price before applying the pricelist
            :param obj product: object of current product record
            :parem float qty: total quentity of product
            :param tuple price_and_rule: tuple(price, suitable_rule) coming from pricelist computation
            :param obj uom: unit of measure of current order line
            :param integer pricelist_id: pricelist id of sale order"""
        PricelistItem = self.env['product.pricelist.item']
        field_name = 'lst_price'
        currency_id = None
        product_currency = None
        if rule_id:
            pricelist_item = PricelistItem.browse(rule_id)
            if pricelist_item.pricelist_id.discount_policy == 'without_discount':
                while pricelist_item.base == 'pricelist' and pricelist_item.base_pricelist_id and pricelist_item.base_pricelist_id.discount_policy == 'without_discount':
                    price, rule_id = pricelist_item.base_pricelist_id.with_context(uom=uom.id).get_product_price_rule(product, qty, self.invoice_id.partner_id)
                    pricelist_item = PricelistItem.browse(rule_id)

            if pricelist_item.base == 'standard_price':
                field_name = 'standard_price'
            if pricelist_item.base == 'pricelist' and pricelist_item.base_pricelist_id:
                field_name = 'price'
                product = product.with_context(pricelist=pricelist_item.base_pricelist_id.id)
                product_currency = pricelist_item.base_pricelist_id.currency_id
            currency_id = pricelist_item.pricelist_id.currency_id
        product_currency = product_currency or(product.company_id and product.company_id.currency_id) or self.env.user.company_id.currency_id
        if not currency_id:
            currency_id = product_currency
            cur_factor = 1.0
        else:
            if currency_id.id == product_currency.id:
                cur_factor = 1.0
            else:
                cur_factor = currency_id._get_conversion_rate(product_currency, currency_id)

        product_uom = self.env.context.get('uom') or product.uom_id.id
        if uom and uom.id != product_uom:
            # the unit price is in a different uom
            uom_factor = uom._compute_price(1.0, product.uom_id)
        else:
            uom_factor = 1.0
        return product[field_name] * uom_factor * cur_factor, currency_id.id

    @api.multi
    def _get_display_price(self, product):
        # TO DO: move me in master/saas-16 on sale.order
        if self.invoice_id.pricelist_id.discount_policy == 'with_discount':
            _logger.info(["product.with_context(pricelist=self.invoice_id", product.with_context(pricelist=self.invoice_id.pricelist_id.id).price])
            return product.with_context(pricelist=self.invoice_id.pricelist_id.id).price
        final_price, rule_id = self.invoice_id.pricelist_id.get_product_price_rule(self.product_id, self.quantity or 1.0, self.invoice_id.partner_id)
        context_partner = dict(self.env.context, partner_id=self.invoice_id.partner_id.id)#, date=self.invoice_id.date_invoice)
        base_price, currency_id = self.with_context(context_partner)._get_real_price_currency(self.product_id, rule_id, self.quantity, self.product_id.uom_id, self.invoice_id.pricelist_id.id)
        if currency_id != self.invoice_id.pricelist_id.currency_id.id:
            base_price = self.env['res.currency'].browse(currency_id).with_context(context_partner).compute(base_price, self.invoice_id.pricelist_id.currency_id)
        # negative discounts (= surcharge) are included in the display price
        return max(base_price, final_price)

    @api.onchange('product_id')
    def price_unit_change(self):
        if self.product_id:
            self.name = self.product_id.name
            product = self.product_id.with_context(
                lang=self.invoice_id.partner_id.lang,
                partner=self.invoice_id.partner_id.id,
                quantity=self.quantity,
                date=self.invoice_id.date_invoice,
                pricelist=self.invoice_id.pricelist_id.id,
                uom=self.product_id.uom_id.id
            )
            if self.invoice_id.pricelist_id and self.invoice_id.partner_id:
                if self.invoice_id.fiscal_position_id:
                    self.price_unit = self._get_display_price(product)
                else:
                    self.price_unit = self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(product), product.taxes_id, self.invoice_line_tax_ids, self.company_id)
