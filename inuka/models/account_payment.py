# -*- coding: utf-8 -*-
from odoo import api, models, fields,_
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    @api.multi
    def post(self):
        SaleOrder = self.env['sale.order']
        for payment in self:
            if payment.payment_type == 'inbound':
                sale_orders = SaleOrder.search([('partner_id', '=', payment.partner_id.id), ('order_status', '=', 'payment')])
                if sale_orders and sale_orders[0].reserve >= 0:
                    sale_orders.write({'order_status': 'open'})
        return super(AccountPayment, self).post()

    @api.onchange('amount', 'currency_id')
    def _onchange_amount(self):
        res = super(AccountPayment, self)._onchange_amount()
        if self._context.get('from_so_register_payment'):
            if not self.currency_id.is_zero(self.amount):
                res['domain']['journal_id'] += [('name', 'in', ('Cash', 'Credit Card'))]
#             self.payment_difference_handling = 'open'
        return res

    def action_validate_invoice_payment(self):
        """ Posts a payment used to pay an invoice. This function only posts the
        payment by default but can be overridden to apply specific post or pre-processing.
        It is called by the "validate" button of the popup window
        triggered on invoice form by the "Register Payment" button.
        """
        if self._context.get('from_so_register_payment') and self._context.get('active_model') == 'sale.order' and self._context.get('active_id'):
            self.post()
            order_id = self.env['sale.order'].browse(self._context.get('active_id'))
            if order_id.reserve >= order_id.amount_total:
                team_id = self.env['crm.team'].search([('name', '=', 'Point of Sale')], limit=1, order="id desc")
                order_id.team_id = team_id.id if team_id else False
                order_id.channel = 'front'
                warehouse_id = self.env['stock.warehouse'].search([('name', '=', 'Bellpark')])
                if not warehouse_id:
                    raise UserError(_('Warning! \nThere is no such warehouse named "Bellpark".'))
                order_id.warehouse_id = warehouse_id.id
                order_id._compute_reserve()
                #Now it creates related ReservedFunds Record.
                order_total = max(order_id.amount_total, order_id.order_total)
                reserve_fund_id = self.env['reserved.fund'].create({
                    'date': fields.Datetime.now(),
                    'desctiption': 'Reservation for %s for Order %s for an amount of %d by %s' % (
                        order_id.partner_id.name, order_id.name, order_id.order_total, order_id.user_id.name),
                    'amount': order_total,
                    'order_id': order_id.id,
                    'customer_id': order_id.partner_id.id,
                })
                order_id.action_confirm()
                order_id.paid = True
                msg = "<b>Fund Reserved</b><ul>"
                msg += "<li>Reservation for %s <br/> for Order %s for an amount of <br/> %s %d by %s" % (
                    order_id.partner_id.name, order_id.name, order_id.company_id.currency_id.symbol, order_id.order_total,
                    order_id.user_id.name)
                msg += "</ul>"
                order_id.message_post(body=msg)
                #The picking will now be created.
                for each_picking in order_id.picking_ids:
                    for move in each_picking.move_lines:
                        move.quantity_done = move.product_uom_qty
#                     each_picking.action_done() #It'll make the pickind done automatically.
                #Invoice will be created.
                invoice_id = order_id.action_invoice_create()
                invoice_id = self.env['account.invoice'].browse(invoice_id[0])
                invoice_id._onchange_partner_id()
                invoice_id.action_invoice_open()
                invoice_id.compute_taxes()
                self.invoice_ids = [(4, invoice_id.id, None)]
            else: return False
            if any(len(record.invoice_ids) != 1 for record in self):
                # For multiple invoices, there is account.register.payments wizard
                raise UserError(_("This method should only be called to process a single invoice's payment."))
            return True
        else:
            super(AccountPayment, self).action_validate_invoice_payment()
