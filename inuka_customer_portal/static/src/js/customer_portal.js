odoo.define('inuka_customer_portal.customer_portal', function (require) {
    "use strict";
    var ajax = require('web.ajax');
    $(document).ready(function () {
        $('#o_mobile_menu_toggle').on('click', function () {
            $('#portal-menu').toggle('slow');
        });
        $('#same_address').on('change', function () {
            if ($(this).is(':checked')) {
                $('.physical_address input').attr('required', false);
                $('.physical_address select').attr('required', false)
                $('.physical_address').hide();
            } else {
                $('.physical_address').show();
                $('.physical_address input').attr('required', 'required');
                $('.physical_address select').attr('required', 'required');
            }
        });
        $('#filter_folder').on('change', function () {
            $(this).parents('.col-md-12').find('button').trigger('click')
        });
        $('.checkout_autoformat input').attr('readonly', true).css('pointer-events', 'none');
        $('.checkout_autoformat select').css('pointer-events', 'none');
        $('.product_price a.btn.btn-default.btn-xs .fa-shopping-cart').on('click', function (e) {
            e.preventDefault();
            var self = $(this);
            var product_id = $(this).parents('.product_price').find('input[name="product_id"]').val();
            var qty = $(this).parents('.product_price').find('input[name="add_qty"]').val();
            ajax.jsonRpc('/add_product_to_cart', "call", {
                'product_id': parseInt(product_id),
                'qty': parseInt(qty)
            }, {'async': false})
                .then(function (result) {
                    var b = $("#my_cart"),
                        c = $(self).parents("form"),
                        d = c.find("img").eq(0);
                    var e = d.clone().offset({
                        top: d.offset().top + 150,
                        left: d.offset().left + 150
                    }).css({
                        opacity: ".9",
                        position: "absolute",
                        height: "50px",
                        width: "50px",
                        "z-index": "999999",
                        "border-radius": "50%"
                    }).appendTo($("body")).animate({
                        top: b.offset().top + 12,
                        left: b.offset().left + 12,
                        width: 75,
                        height: 75
                    }, 1e3, "easeInOutExpo");
                    setTimeout(function () {
                        b.effect("shake", {
                            times: 2
                        }, 400)
                    }, 1500), e.animate({
                        width: 0,
                        height: 0
                    }, function () {
                        $(this).detach()
                    });
                    if (isNaN(parseInt($("#my_cart").find('.my_cart_quantity.label.label-primary').text()))) {
                        var cart_item = 0
                    } else {
                        var cart_item = parseInt($("#my_cart").find('.my_cart_quantity.label.label-primary').text());
                    }
                    $("#my_cart").find('.my_cart_quantity.label.label-primary').text(cart_item + parseInt(qty));
                    $(self).parents('.product_price').find('input[name="add_qty"]').val('').val('1');
                });
        });
        var dteNow = new Date();
        var endYear = dteNow.getFullYear();
        var startYear = parseInt(endYear) - 80;
        var year_range = String(startYear) + ':' + String(endYear);
        $("input[data-type='date']").datepicker({
            changeMonth: true,
            changeYear: true,
            yearRange: year_range,
            minDate: new Date(1900, 1 - 1, 1), maxDate: '-18Y',
            dateFormat: 'mm-dd-yy',
            defaultDate: new Date(1970, 1 - 1, 1),
        });

        function check_unique_data(value, element) {
            ajax.jsonRpc('/check_unique_data', "call", value, {'async': false})
                .then(function (result) {
                    if (result) {
                        $(element).parent().find('.danger').remove();
                        $(element).parent().append('<p class="danger" style="color:red">' + result + ' Already Exist in system.</p>');
                        $(document).find('button[type="submit"]').css('pointer-events', 'none')
                    } else {
                        $(element).parent().find('.danger').remove();
                        $(document).find('button[type="submit"]').css('pointer-events', 'auto')
                    }
                });
        }

        if (typeof $(document).find('.registration_form').html() != 'undefined') {
            $("input[name='email']").on('change', function () {
                var email = $(this).val();
                check_unique_data({'type': 'email', 'data': email}, $(this));
            });
            $('body').bind("DOMSubtreeModified", '.selected-dial-code', function (e) {
                e.preventDefault();
                e.stopPropagation();
                var code = $('.selected-dial-code').text();
                var mobile = $("input[name='mobile']").val();
                if (code != $("input[name='countryCode']").val()) {
                    $("input[name='countryCode']").val(code);
                    check_unique_data({'type': 'mobile', 'data': code + mobile}, $(this));
                }

            });

            $("input[name='mobile']").on('change', function () {
                var mobile = $(this).val();
                var code = $('.selected-dial-code').text().substr(1);
                $("input[name='countryCode']").val(code);
                check_unique_data({'type': 'mobile', 'data': code + mobile}, $(this));
            });
        }

        if ($('.o_register_member_details').length) {
            var state_options = $("select[name='state_id']:enabled option:not(:first)");
            $('.o_register_member_details').on('change', "select[name='country_id']", function () {
                var select = $("select[name='state_id']");
                state_options.detach();
                var displayed_state = state_options.filter("[data-country_id=" + ($(this).val() || 0) + "]");
                var nb = displayed_state.appendTo(select).show().size();
                select.parent().toggle(nb >= 1);
            });
            $('.o_register_member_details').find("select[name='country_id']").change();
        }
        if ($('.o_register_member_details_shipping').length) {
            var state_options = $("select[name='delivery_state_id']:enabled option:not(:first)");
            $('.o_register_member_details_shipping').on('change', "select[name='delivery_country_id']", function () {
                var select = $("select[name='delivery_state_id']");
                state_options.detach();
                var displayed_state = state_options.filter("[data-country_id=" + ($(this).val() || 0) + "]");
                var nb = displayed_state.appendTo(select).show().size();
                select.parent().toggle(nb >= 1);
            });
            $('.o_register_member_details_shipping').find("select[name='delivery_country_id']").change();
        }

        function readURL(input) {
            if (input.files && input.files[0]) {
                var reader = new FileReader();
                reader.onload = function (e) {
                    $('#imagePreview').css('background-image', 'url(' + e.target.result + ')');
                    $('#imagePreview').hide();
                    $('#imagePreview').fadeIn(650);
                }
                reader.readAsDataURL(input.files[0]);
            }
        }

        $('.search_icon').on('click', function () {
            $(document).find('.o_portal_search_panel').removeClass('hidden-xs');
            $(this).hide();
        });
        $("#imageUpload").change(function () {
            readURL(this);
        });

        $('.form-control.number').keypress(function (event) {
            if (event.which < 46 && event.which != 8
                || event.which > 59 && event.which != 8) {
                event.preventDefault();
            }
            if (event.which == 46 && $(this).val().indexOf('.') != -1) {
                event.preventDefault();
            }
        });

        var telInput = $("#mobile"),
            errorMsg = $("#error-msg"),
            validMsg = $("#valid-msg");

// initialise plugin
        telInput.intlTelInput({
            // allowExtensions: true,
            // formatOnDisplay: true,
            // autoFormat: true,
            // autoHideDialCode: true,
            defaultCountry: "za",
            // nationalMode: false,
            numberType: "MOBILE",
            onlyCountries: ['ao', 'bw', 'ls', 'mw', 'mz', 'na', 'ng', 'za', 'sz', 'tz', 'ug', 'zm', 'zw'],
            preventInvalidNumbers: true,
            separateDialCode: true,
            initialCountry: "za",
            // utilsScript: "https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/11.0.9/js/utils.js"
        });

        var reset = function () {
            telInput.removeClass("error");
            errorMsg.addClass("hide");
            validMsg.addClass("hide");
        };
        telInput.blur(function () {
            reset();
            if ($.trim(telInput.val())) {
                if (telInput.intlTelInput("isValidNumber")) {
                    validMsg.removeClass("hide");
                } else {
                    telInput.addClass("error");
                    errorMsg.removeClass("hide");
                }
            }
        });
        telInput.on("keyup change", reset);

    });
});
