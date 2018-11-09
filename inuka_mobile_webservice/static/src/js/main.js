odoo.define('inuka_mobile_webservice.main', function (require) {
    "use strict";
    var ajax = require('web.ajax');
    $(document).ready(function () {
        $('#webservice_list').on('change', function (e) {
            e.preventDefault();
            var self = $(this);
            var service = $(this).val();
            ajax.jsonRpc('/get_require_parameters', "call", {
                'service': service,
            }, {'async': false})
                .then(function (result) {
                    $(document).find('.request_param').remove();
                    $(document).find('.submit_button').remove();
                    console.log(result)
                    for (var i = 0; i <= result.length; i++) {
                        if (result[i]) {
                            var html = '<div class="form-group request_param">' +
                                '<label for="' + result[i]['param'] + '">' + result[i]['param'] + '</label>' +
                                '<input type="text" class="form-control" name="' + result[i]['param'] + '"/>' +
                                '</div>';
                            $(document).find('#request_param_list').append(html)
                        }
                    }
                    $(document).find('#request_param_list').append('<div class="form-group submit_button">' +
                        '<button type="submit" class="btn btn-primary pull-right">Submit</button>' +
                        '</div>')
                });
        });
    });
});
