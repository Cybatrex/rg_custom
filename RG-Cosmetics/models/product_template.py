from odoo import models, fields, _


class product_template(models.Model):
    _inherit = 'product.template'

    fragrance = fields.Text(string="Fragrance")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: