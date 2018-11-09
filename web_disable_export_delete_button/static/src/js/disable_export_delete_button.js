odoo.define("web_disable_export_delete_button", function (require) {
"use strict";

    var core = require("web.core");
    var Sidebar = require('web.Sidebar');
    var ListController = require("web.ListController");
    var _t = core._t;
    var session = require("web.session");

    ListController.include({
        willStart: function () {
            var self = this;
            var def1 = this.getSession().user_has_group('web_disable_export_delete_button.group_export_button').then(function (has_group) {
                if (has_group) {
                    self.has_export_group = true;
                } else {
                    self.has_export_group = false;
                }
            });
            var def2 = this.getSession().user_has_group('web_disable_export_delete_button.group_delete_button').then(function (has_group) {
                if (has_group) {
                    self.has_delete_group = true;
                } else {
                    self.has_delete_group = false;
                }
            });
            return $.when(def1, def2);
        },
        /**
         * Render the sidebar (the 'action' menu in the control panel, right of the
         * main buttons)
         *
         * @param {jQuery Node} $node
         */
        renderSidebar: function ($node) {
            if (this.hasSidebar && !this.sidebar) {
                var other = [];
                
                if (this.has_export_group || session.is_superuser) {
                    other.push({
                        label: _t("Export"),
                        callback: this._onExportData.bind(this)
                    });
                }
                
                if (this.archiveEnabled) {
                    other.push({
                        label: _t("Archive"),
                        callback: this._onToggleArchiveState.bind(this, true)
                    });
                    other.push({
                        label: _t("Unarchive"),
                        callback: this._onToggleArchiveState.bind(this, false)
                    });
                }
                
                if (this.is_action_enabled('delete')) {
                    
                    if (this.has_delete_group || session.is_superuser) {
                        other.push({
                            label: _t('Delete'),
                            callback: this._onDeleteSelectedRecords.bind(this)
                        });
                    }
                }
                this.sidebar = new Sidebar(this, {
                    editable: this.is_action_enabled('edit'),
                    env: {
                        context: this.model.get(this.handle, {raw: true}).getContext(),
                        activeIds: this.getSelectedIds(),
                        model: this.modelName,
                    },
                    actions: _.extend(this.toolbarActions, {other: other}),
                });

                this.sidebar.appendTo($node);
                this._toggleSidebar();

            }
        }
    });
});
