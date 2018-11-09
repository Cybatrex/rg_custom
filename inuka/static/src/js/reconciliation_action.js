odoo.define('account.inuka.ReconciliationClientAction', function (require) {
"use strict";
var core = require('web.core');

var StatementAction = core.action_registry.get('bank_statement_reconciliation_view');		

StatementAction.include({

	willStart: function () {
		var self = this;
		var def = this._super.apply(this, arguments);
		return def.then(function(){
            return self._rpc({
                model: 'account.reconcile.model',
                method: 'get_record_id',
                // kwargs: {xmlid: 'inuka.account_reconcile_model'},
            }).then(function(res_id){
            	self.reconcileModelID = res_id;
            });
		})
    },
	start: function () {
		var def = this._super.apply(this, arguments);
		this._set_account();
		return def
	},
    _set_account: function () {
        var self = this;

        var handles = _.compact(_.map(this.model.lines,  function (line, handle) {
                return line.reconciled ? null : handle;
            }));
        _.each(handles, function(handle){
            var line = self.model.getLine(handle);
            var widget = self._getWidget(handle);
            if(widget && widget.fields.partner_id.value){
                self.model.changeMode(handle, 'create').always(function () { 
                    self.model.quickCreateProposition(handle, self.reconcileModelID).then(function(){
                        self._getWidget(handle).update(line);
                    })
                    // self._getWidget(handle).update(line);
                });
            }

        });
	},

})
});
