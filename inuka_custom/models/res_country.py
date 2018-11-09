from openerp import fields, models, api
import logging
_logger = logging.getLogger(__name__)

class res_country(models.Model):

    _inherit = 'res.country'

    members = fields.Boolean('Members?')
