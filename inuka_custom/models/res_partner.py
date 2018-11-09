from openerp import fields, models, api
import logging
_logger = logging.getLogger(__name__)

class res_partner(models.Model):

    _inherit = 'res.partner'

#     @api.onchange('customer')
#     def _default_candidate(self):
#         if self.customer and not self.status:
#             self.status = 'candidate'

    mentor_id = fields.Many2one("res.users", "Mentor")
    #country_id = fields.Many2one("res.country", placeholder="Country", domain=lambda self:self._get_country())
    region = fields.Char("Region")
#     status = fields.Selection([
#         ('candidate', 'Candidate'),
#         ('new', 'New'),
#         ('junior', 'Junior'),
#         ('senior', 'Senior'),
#         ('pearl', 'Pearl'),
#         ('ruby', 'Ruby'),
#         ('emerald', 'Emerald'),
#         ('sapphire', 'Sapphire'),
#         ('diamond', 'Diamond'),
#         ('double_diamond', 'Double Diamond'),
#         ('triple_diamond', 'Triple Diamond'),
#         ('exective_diamond', 'Exective Diamond'),
#         ('presidential', 'Presidential'),
#         ('cancelled', 'Cancelled'),
#         ('discontinued', 'Discontinued')
#         ], string='Status', track_visibility='onchange')

    @api.onchange('upline')
    def upline_change(self):
        if self.upline:
            self.upline_id = self.upline.ref
            
    @api.onchange('ref')
    def _onchange_ref(self):
        if self.ref:
            self.ref = self.ref.upper()
    

    @api.onchange('country_id')
    def _get_country(self):
        res_country_obj = self.env['res.country']
        countries = []
        if self.supplier == True:
            countries = res_country_obj.search([('id', '>', 0)])
        if self.customer == True:
            countries = res_country_obj.search([('members', '=', True)])
        ids = []
        for country in countries:
            ids.append(country.id)
        return {'domain':{'country_id': [('id', 'in', ids)]}}

    @api.model
    def create(self, vals):
        if vals.get('parent_id'):
            vals['customer'] = False
        if self._context.get('from_user'):
            vals['customer'] = False
        if not vals.get('status'):
            vals['status'] = 'candidate'
        return super(res_partner, self).create(vals)

    @api.multi
    def write(self, vals):
        first_name = vals.get('first_name', '')
        last_name = vals.get('last_name', '')
        if first_name and last_name:
            vals['name'] = ''
            if first_name:
                vals['name'] += (first_name)
            if last_name:
                vals['name'] += ' ' + (last_name)
            vals['name'] += ' (' + (self.ref) +')'
        if first_name and not last_name:
            vals['name'] = ''
            if first_name:
                vals['name'] += (first_name)
                vals['name'] += ' ' + (self.last_name)
                vals['name'] += ' (' + (self.ref) +')'
        if last_name and not first_name:
            vals['name'] = ''
            if last_name:
                vals['name'] += (self.first_name)
                vals['name'] += ' ' + (last_name)
                vals['name'] += ' (' + (self.ref) +')'
        return super(res_partner, self).write(vals)
