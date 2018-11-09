odoo.define('point_of_sale.membership_pos_list', function (require) {
"use strict";

var models = require('point_of_sale.models');
var screens = require('point_of_sale.screens');
var gui = require('point_of_sale.gui');
var core = require('web.core');
var QWeb = core.qweb;
var _t = core._t;

models.load_fields('product.product','pv');


screens.OrderWidget.include({
	update_summary: function(){
        var order = this.pos.get_order();
        if (!order.get_orderlines().length) {
            return;
        }

        var total     = order ? order.get_total_with_tax() : 0;
        var taxes     = order ? total - order.get_total_without_tax() : 0;
        var category_pv_total = 0;

        _.each(order.get_orderlines(), function(orderline) {
            category_pv_total += orderline.product.pv * orderline.quantity;
        });

        this.el.querySelector('.summary .total > .value').textContent = this.format_currency(total);
        this.el.querySelector('.summary .total .subentry .value').textContent = this.format_currency(taxes);
        this.el.querySelector('.summary .total_pv_line .subentry .value').textContent = category_pv_total;
    }
});

screens.ActionpadWidget.include({
	renderElement: function() {
        var self = this;
        this._super();
        this.$('.pay').click(function(){
            var order = self.pos.get_order();	     
            var has_valid_product_lot = _.every(order.orderlines.models, function(line){
                return line.has_valid_product_lot();
            });
            if (!self.pos.get_client()) {
                self.gui.show_screen('products');
            	self.gui.show_popup('error',{
                    'title': _t('Customer is not selected'),
                    'body':  _t('You must need to select customer to proceed further.'),
                });
            }
            else if(!has_valid_product_lot){
                self.gui.show_popup('confirm',{
                    'title': _t('Empty Serial/Lot Number'),
                    'body':  _t('One or more product(s) required serial/lot number.'),
                    confirm: function(){
                        self.gui.show_screen('payment');
                    },
                });
            }else{
                self.gui.show_screen('payment');
            }
            if (self.pos.get_client()) {
                self._rpc({
                    model: 'pos.config',
                    method: 'calculate_reserve',
                    args: [self.pos.get_client().id],
                }).then(function (result) {
                    $('.reserve_amount').text('('+result+')').css('color','red');
                });
            }
        });
        this.$('.set-customer').click(function(){
            self.gui.show_screen('clientlist');
        });
    }
});

var PaymentScreen = screens.PaymentScreenWidget.extend({
    init: function(parent, options) {
        this._super(parent, options);
    	this.click_invoice();
    }
});
gui.define_screen({name:'payment', widget: PaymentScreen});

});