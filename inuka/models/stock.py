# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StockQant(models.Model):
    _inherit = "stock.move.line"
    
    package_id = fields.Many2one(index=True)
    product_id = fields.Many2one(index=True)
    location_id = fields.Many2one(index=True)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"
    
    move_id = fields.Many2one(index=True)
    product_id = fields.Many2one(index=True)
    lot_id = fields.Many2one(index=True)
    location_id = fields.Many2one(index=True)
    package_id = fields.Many2one(index=True)
    picking_id = fields.Many2one(index=True)


class PickingType(models.Model):
    _inherit = "stock.picking.type"

    # Statistics for the kanban view
    count_bulk_waiting = fields.Integer(compute='_compute_bulk_count')
    count_bulk_ready = fields.Integer(compute='_compute_bulk_count')
    count_bulk_late = fields.Integer(compute='_compute_bulk_count')

    def _compute_bulk_count(self):
        today = fields.Datetime.now()
        Bulk = self.env['bulk.master']
        waiting = Bulk.search_count([('state', '=', 'confirmed')])
        ready = Bulk.search_count([('state', '=', 'ready')])
        late = Bulk.search_count([('state', 'not in', ['done', 'cancelled']), ('schedule_date', '<', today)])
        for record in self:
            record.count_bulk_waiting = waiting
            record.count_bulk_ready = ready
            record.count_bulk_late = late

    @api.multi
    def view_bulk_waiting(self):
        self.ensure_one()
        waiting_bulk = self.env['bulk.master'].search([('state', '=', 'confirmed')])
        action = self.env.ref('inuka.action_bulk_master_form').read()[0]
        action['domain'] = [('id', 'in', waiting_bulk.ids)]
        return action

    @api.multi
    def view_bulk_ready(self):
        self.ensure_one()
        bulk_ready = self.env['bulk.master'].search([('state', '=', 'ready')])
        action = self.env.ref('inuka.action_bulk_master_form').read()[0]
        action['domain'] = [('id', 'in', bulk_ready.ids)]
        return action

    @api.multi
    def view_bulk_late(self):
        self.ensure_one()
        today = fields.Datetime.now()
        bulk_late = self.env['bulk.master'].search([('state', 'not in', ['done', 'cancelled']), ('schedule_date', '<', today)])
        action = self.env.ref('inuka.action_bulk_master_form').read()[0]
        action['domain'] = [('id', 'in', bulk_late.ids)]
        return action


class Picking(models.Model):
    _inherit = 'stock.picking'

    bulk_master_id = fields.Many2one("bulk.master", string="Bulk")
    team_id = fields.Many2one('crm.team', 'Sales Team')

    @api.multi
    def button_validate(self):
        context = dict(self.env.context or {})
        if not context.get('from_bulk') and any(picking.bulk_master_id.id != False for picking in self):
            raise UserError(_("You cannot validate if part of bulk."))
        if self.picking_type_id and self.picking_type_id.code == 'outgoing' and self.carrier_id:
            carrier_ids = self.env['delivery.carrier'].search([('name', 'in', ('Free delivery charges', 'Office Collect or Own Courier', 'Part of Bulk'))])
            if self.carrier_id not in carrier_ids and not self.carrier_tracking_ref:
                raise ValidationError(_("Warning!\nPlease complete the waybill number."))
        return super(Picking, self).button_validate()


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    blocked_for_delivery = fields.Boolean("Blocked for Delivery")
    free_over_pv = fields.Boolean("Free if PV Total are above")
    amount_pv = fields.Float("PV Amount")

    def rate_shipment(self, order):
        ''' Compute the price of the order shipment

        :param order: record of sale.order
        :return dict: {'success': boolean,
                       'price': a float,
                       'error_message': a string containing an error message,
                       'warning_message': a string containing a warning message}
                       # TODO maybe the currency code?
        '''
        self.ensure_one()
        if hasattr(self, '%s_rate_shipment' % self.delivery_type):
            res = getattr(self, '%s_rate_shipment' % self.delivery_type)(order)
            # apply margin on computed price
            res['price'] = res['price'] * (1.0 + (float(self.margin) / 100.0))

            # free when order PV is large enough
            if res['success'] and self.free_over_pv and order.total_pv >= self.amount_pv:
                res['warning_message'] = _('Info:\nThe shipping is free because the order PV Total amount exceeds(or equal) %.2f.\n(The actual shipping cost is: %.2f)') % (self.amount_pv, res['price'])
                res['price'] = 0.0

            # free when order is large enough
            if res['success'] and self.free_over and order._compute_amount_total_without_delivery() >= self.amount:
                res['warning_message'] = _('Info:\nThe shipping is free because the order amount exceeds %.2f.\n(The actual shipping cost is: %.2f)') % (self.amount, res['price'])
                res['price'] = 0.0
            return res


class Inventory(models.Model):
    _inherit = "stock.inventory"

    description = fields.Text()


class StockMove(models.Model):
    _inherit = "stock.move"

    team_id = fields.Many2one('crm.team', 'Sales Team')

    def _get_new_picking_values(self):
        """ Prepares a new picking for this move as it could not be assigned to
        another picking. This method is designed to be inherited. """
        res = super(StockMove, self)._get_new_picking_values()
        res['team_id'] = self.team_id.id
        return res


class ProcurementRule(models.Model):
    """ A rule describe what a procurement should do; produce, buy, move, ... """
    _inherit = 'procurement.rule'

    def _get_stock_move_values(self, product_id, product_qty, product_uom, location_id, name, origin, values, group_id):
        res = super(ProcurementRule, self)._get_stock_move_values(product_id=product_id, product_qty=product_qty, product_uom=product_uom,
            location_id=location_id, name=name, origin=origin, values=values, group_id=group_id)
        if res.get('group_id'):
            sale_order = self.env['procurement.group'].browse(group_id).sale_id
            res['team_id'] = sale_order.team_id.id
        return res
