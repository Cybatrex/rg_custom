from openerp import fields, models, api
import logging
_logger = logging.getLogger(__name__)

class res_company(models.Model):

    _inherit = 'res.company'

    vat = fields.Char('VAT')
    customer_export = fields.Char('Customer Export No')

    def get_company(self, invoice_id):
        for rec in invoice_id:
            if rec.partner_shipping_id.country_id.name == "Namibia":
                return self.sudo().search([('name', '=', 'INUKA Namibia')])
        return self

    def get_printed(self, invoice_id):
        if invoice_id:
            if invoice_id.state == 'open':
                invoice_id.printed = True
        return invoice_id
