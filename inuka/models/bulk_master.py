# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, Warning


class BulkMaster(models.Model):
    _name = 'bulk.master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Bulk Master'

    name = fields.Char(string="Reference")
    partner_id = fields.Many2one("res.partner", string="Member", required=True, track_visibility='always', readonly=True, states={'draft': [('readonly', False)]})
    member_id = fields.Char(related="partner_id.ref", string="Member ID", required=True, readonly=True, states={'draft': [('readonly', False)]})
    partner_shipping_id = fields.Many2one("res.partner", string="Delivery Address", readonly=True, states={'draft': [('readonly', False)]})
    bulk_type = fields.Selection([
        ('bulk', 'Bulk'),
        ('consolidated', 'Consolidated')
        ], string='Type', required=True, readonly=True, states={'draft': [('readonly', False)]})
    date = fields.Datetime("Date", readonly=True, required=True, default=fields.Datetime.now(), copy=False)
    schedule_date = fields.Datetime("Scheduled Date", readonly=True, states={'draft': [('readonly', False)]})
    user_id = fields.Many2one("res.users", string="Managed By", required=True, default=lambda self: self.env.uid, track_visibility='always', readonly=True, states={'draft': [('readonly', False)]})
    product_total = fields.Float(compute="_compute_order_totals", string="Products Total", track_visibility='onchange')
    shipping_total = fields.Float(compute="_compute_order_totals", string="Shipping Total", track_visibility='onchange', store=True)
    unpaid_total = fields.Float(compute="_compute_order_totals", string="Unpaid Amount")
    pv_total = fields.Float(compute="_compute_order_totals", string="Total PV", track_visibility='onchange', store=True)
    waybill = fields.Char("Waybill", readonly=True, states={'draft': [('readonly', False)], 'confirmed': [('readonly', False)]})
    carrier_id = fields.Many2one("delivery.carrier", string="Dispatch Method", required=True, readonly=True, states={'draft': [('readonly', False)]})
    unpaid_pv = fields.Float(compute="_compute_order_totals", string="Unpaid PV",)
    bulk_lock = fields.Boolean("Bulk Lock", readonly=True, copy=False)
    pack_lock = fields.Boolean("Pack Lock", readonly=True, copy=False)
    description = fields.Text("Comment")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Waiting'),
        ('ready', 'Ready'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
        ], string='Status', default='draft', track_visibility='onchange')
    sale_orders = fields.One2many('sale.order', 'bulk_master_id', string="Orders", readonly=True, copy=False)
    sale_order_count = fields.Integer(compute="_compute_sale_order_count", string="Sale Orders")
    delivery_count = fields.Integer(compute='_compute_picking_ids', string='Delivery Orders')
    free_shipping = fields.Boolean("Free Shipping", readonly=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)
    is_dispatch_group = fields.Boolean(compute="_compute_is_dispatch_group")
    team_id = fields.Many2one('crm.team', 'Sales Team')

    @api.model
    def create(self, vals):
        res = super(BulkMaster, self).create(vals)
        if self._context.get('quick_create'):
            res.button_confirm()
        return res

    def _compute_is_dispatch_group(self):
        for bulk in self:
            if bulk.user_has_groups('inuka.dispatch_group'):
                bulk.is_dispatch_group = True
            else:
                bulk.is_dispatch_group = False
    
    @api.depends('sale_orders', 'sale_orders.amount_total', 'sale_orders.shipping_cost', 'sale_orders.total_pv', 'sale_orders.paid')
    def _compute_order_totals(self):
        for bulk in self:
            product_total = shipping_total = unpaid_total = pv_total = unpaid_pv = 0.0
            for order in bulk.sale_orders:
                product_total += order.amount_total
                shipping_total += order.shipping_cost
                pv_total += order.total_pv
                if not order.paid:
                    unpaid_total += order.amount_total
                    unpaid_pv += order.total_pv
            bulk.product_total = product_total
            bulk.shipping_total = shipping_total
            bulk.unpaid_total = unpaid_total
            bulk.pv_total = pv_total
            bulk.unpaid_pv = unpaid_pv

    def _compute_sale_order_count(self):
        for bulk in self:
            bulk.sale_order_count = len(bulk.sale_orders)

    def _compute_picking_ids(self):
        for bulk in self:
            count = 0
            for order in bulk.sale_orders:
                count += len(order.picking_ids)
            bulk.delivery_count = count

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        context = dict(self.env.context or {})
        order_type = context.get('order_type')

        if order_type and order_type == 'bulk':
            recs = self.search([('name', 'ilike', name), ('bulk_type', '=', 'bulk'), ('state', '=', 'confirmed'), ('bulk_lock', '=', False), ('pack_lock', '=', False)] + args, limit=limit)
        elif order_type and order_type == 'consolidated':
            partner_id = context.get('partner_id')
            recs = self.search([('name', 'ilike', name), ('bulk_type', '=', 'consolidated'), ('state', '=', 'confirmed'), ('partner_id', '=', partner_id), ('bulk_lock', '=', False), ('pack_lock', '=', False)] + args, limit=limit)
        else:
            recs = self.search(args, limit=limit)
        return recs.name_get()

    @api.multi
    def view_sale_orders(self):
        self.ensure_one()
        orders = self.mapped('sale_orders')
        action = self.env.ref('sale.action_orders').read()[0]
        action['domain'] = [('id', 'in', orders.ids)]
        return action

    @api.multi
    def view_delivery_orders(self):
        self.ensure_one()
        action = self.env.ref('stock.action_picking_tree_all').read()[0]
        pickings = self.sale_orders.mapped('picking_ids')
        action['domain'] = [('id', 'in', pickings.ids)]
        return action

    @api.multi
    def button_confirm(self):
        for bulk in self:
            if bulk.bulk_type == 'bulk' and not bulk.partner_id.bulk_custodian:
                raise UserError(_('Member is not a Bulk Custodian.'))
            name = self.env.ref('inuka.seq_bulk_master').next_by_id() + '/' + bulk.partner_id.ref
            bulk.write({'name': name, 'state': 'confirmed'})

    @api.multi
    def button_print(self):
        self.ensure_one()
        return self.env.ref('inuka.action_report_delivery_bulk').report_action(self)

    @api.multi
    def button_bulk_lock(self):
        self.write({'bulk_lock': True})

    @api.multi
    def button_pack_lock(self):
        for bulk in self:
            if not (bulk.shipping_total > 1 or bulk.pv_total == 45 or bulk.pv_total > 50 or bulk.free_shipping):
                raise UserError(_('Minimum PV’s required not met / Shipping required.'))
            if not bulk.waybill:
                raise UserError(_('Please enter a waybill number.'))
            if any(order.state == 'draft' for order in bulk.sale_orders):
                raise UserError(_("All orders should be paid and confirmed to continue."))
        self.write({'pack_lock': True, 'state': 'ready'})

    @api.multi
    def button_bulk_unlock(self):
        self.write({'bulk_lock': False})

    @api.multi
    def button_pack_unlock(self):
        self.write({'pack_lock': False, 'state': 'confirmed'})

    @api.multi
    def button_validate(self):
        self.ensure_one()

        if self.bulk_type == 'bulk':
            if self.partner_id.mobile:
                sms_template = self.env.ref('sms_frame.sms_template_inuka_international')
                msg_compose = self.env['sms.compose'].create({
                    'record_id': self.id,
                    'model': 'bulk.master',
                    'sms_template_id': sms_template.id,
                    'from_mobile_id': self.env.ref('sms_frame.sms_number_inuka_international').id,
                    'to_number': self.partner_id.mobile,
                    'sms_content': """ INUKA Courier bulk dispatch^ %s %s, we dispatched today^ (Ref: %s)^Courier could call to confirm delivery^Allow 4-7 days^Info 27219499850""" % (self.partner_id.first_name, self.partner_id.last_name, self.name)
                })
                msg_compose.send_entity()
            for order in self:
                if order.partner_id.mobile:
                    sms_template = self.env.ref('sms_frame.sms_template_inuka_international')
                    msg_compose = self.env['sms.compose'].create({
                        'record_id': order.id,
                        'model': 'sale.order',
                        'sms_template_id': sms_template.id,
                        'from_mobile_id': self.env.ref('sms_frame.sms_number_inuka_international').id,
                        'to_number': order.partner_id.mobile,
                        'sms_content': """ INUKA Courier bulk dispatch^ %s %s, your order was sent today^Call %s %s on %s  to collect^Allow 4 - 7days^Info 27219499850""" % (order.partner_id.first_name, order.partner_id.last_name, self.partner_id.first_name, self.partner_id.last_name, self.partner_id.mobile)
                    })
                    msg_compose.send_entity()
        elif self.bulk_type == 'consolidated':
            if self.partner_id.mobile:
                sms_template = self.env.ref('sms_frame.sms_template_inuka_international')
                msg_compose = self.env['sms.compose'].create({
                    'record_id': self.id,
                    'model': 'bulk.master',
                    'sms_template_id': sms_template.id,
                    'from_mobile_id': self.env.ref('sms_frame.sms_number_inuka_international').id,
                    'to_number': self.partner_id.mobile,
                    'sms_content': """ INUKA Courier Dispatch^ %s %s, your orders were sent today^TrackNo %s ^Courier could call to confirm delivery^Allow 4-7days^Info 27219499850""" % (self.partner_id.first_name, self.partner_id.last_name, self.waybill)
                })
                msg_compose.send_entity()

        pickings = self.sale_orders.mapped('picking_ids')

        if any(x.picking_type_id.code != 'outgoing' and x.state != 'done' for x in pickings):
            raise Warning(_("Warning!\nYou can not Validate if there are outstanding Pick & Pack operations pending."))
        # Done the picking
        pickings.action_confirm()
        pickings.force_assign()
        for picking in pickings:
            for move in picking.move_lines:
                move.write({'quantity_done': move.product_uom_qty})
            picking.write({'carrier_tracking_ref': self.waybill})
            picking.with_context(from_bulk=True).button_validate()
        self.write({'state': 'done'})

    @api.multi
    def button_approve(self):
        if not self.user_has_groups('inuka.group_approval_for_free_shipping'):
            raise UserError(_("Access Denied: You don't have rights to approve for free shipping."))
        for bulk in self:
            bulk.free_shipping = True
            msg = "<ul>"
            msg += "<li>Approved for Free Shipping by %s " % (bulk.env.user.name)
            msg += "</ul>"
            bulk.message_post(body=msg)

    @api.multi
    def button_cancel(self):
        self.write({'state': 'cancelled'})

    @api.multi
    def button_reset(self):
        self.write({'state': 'draft', 'bulk_lock': False, 'pack_lock': False})
