# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    category_pv = fields.Float('Category PV')


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    pv = fields.Float('PV')
    product_fragrance = fields.Text("Fragrance")
