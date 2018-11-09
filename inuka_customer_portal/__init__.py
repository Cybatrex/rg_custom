from . import models
from . import controllers
from odoo.api import Environment, SUPERUSER_ID
from odoo import api


def post_init_check(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    param_obj = env['ir.config_parameter']
    param_obj.sudo().set_param('auth_signup.reset_password', True)
    reset_password = bool(param_obj.sudo().get_param('auth_signup.reset_password'))
    param_obj.sudo().set_param('website_sale.automatic_invoice', True)
    automatic_invoice = bool(param_obj.sudo().get_param('website_sale.automatic_invoice'))
