/* For datatable view */

var datatableview = (function(){
    return {
        auto_initialize: undefined,
        autoInitialize: false,  // Legacy name
        defaults: {
            "serverSide": true,
            "paging": true
        },

        makeXEditable: function(options) {
            var options = $.extend({}, options);
            if (!options.ajaxOptions) {
                options.ajaxOptions = {}
            }
            if (!options.ajaxOptions.headers) {
                options.ajaxOptions.headers = {}
            }
            options.ajaxOptions.headers['X-CSRFToken'] = datatableview.getCookie('csrftoken');
            options.error = function (data) {
                var response = data.responseJSON;
                if (response.status == 'error') {
                    var errors = $.map(response.form_errors, function(errors, field){
                        return errors.join('\n');
                    });
                    return errors.join('\n');
                }
            };
            return function(nRow, mData, iDisplayIndex) {
                $('td a[data-xeditable]', nRow).editable(options);
                return nRow;
            }
        },
        make_xeditable: makeXEditable,  // Legacy name

        getCookie: function(name) {
            var cookieValue = null;
            if (document.cookie && document.cookie != '') {
                var cookies = document.cookie.split(';');
                for (var i = 0; i < cookies.length; i++) {
                    var cookie = jQuery.trim(cookies[i]);
                    // Does this cookie string begin with the name we want?
                    if (cookie.substring(0, name.length + 1) == (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        },

        initialize: function($$, opts) {
            if (typeof window.console === "undefined" || typeof window.console.log === "undefined") {
                console = {
                    log: function(){},
                    info: function(){}
                };
            }
            var optionsNameMap = {
                'name': 'name',
                'config-sortable': 'orderable',
                'config-sorting': 'order',
                'config-visible': 'visible',
                'config-searchable': 'searchable'
            };

            $$.each(function(){
                var datatable = $(this);
                var columnOptions = [];
                var sortingOptions = [];

                datatable.find('thead th').each(function(){
                    var header = $(this);
                    var options = {};
                    for (var i = 0; i < header[0].attributes.length; i++) {
                        var attr = header[0].attributes[i];
                        if (attr.specified && /^data-/.test(attr.name)) {
                            var name = attr.name.replace(/^data-/, '');
                            var value = attr.value;

                            // Typecasting out of string
                            name = optionsNameMap[name];
                            if (/^b/.test(name)) {
                                value = (value === 'true');
                            }

                            if (name == 'order') {
                                // This doesn't go in the columnOptions
                                var sort_info = value.split(',');
                                sort_info[1] = parseInt(sort_info[1]);
                                sortingOptions.push(sort_info);
                                continue;
                            }

                            options[name] = value;
                        }
                    }
                    columnOptions.push(options);
                });

                // Arrange the sorting column requests and strip the priority information
                sortingOptions.sort(function(a, b){ return a[0] - b[0] });
                for (var i = 0; i < sortingOptions.length; i++) {
                    sortingOptions[i] = sortingOptions[i].slice(1);
                }

                options = $.extend({}, datatableview.defaults, opts, {
                    "order": sortingOptions,
                    "columns": columnOptions,
                    "pageLength": datatable.attr('data-page-length'),
                    "infoCallback": function(oSettings, iStart, iEnd, iMax, iTotal, sPre){
                        $("#" + datatable.attr('data-result-counter-id')).html(parseInt(iTotal).toLocaleString());
                        var infoString = oSettings.oLanguage.sInfo.replace('_START_',iStart).replace('_END_',iEnd).replace('_TOTAL_',iTotal);
                        if (iMax != iTotal) {
                            infoString += oSettings.oLanguage.sInfoFiltered.replace('_MAX_',iMax);
                        }
                        return infoString;
                    }
                });
                options.ajax = $.extend(options.ajax, {
                    "url": datatable.attr('data-source-url'),
                    "type": datatable.attr('data-ajax-method') || 'GET',
                    "beforeSend": function(request){
                        request.setRequestHeader("X-CSRFToken", datatableview.getCookie('csrftoken'));
                    }
                });
                try {
                    options = confirm_datatable_options(options, datatable);
                } catch (e) {

                }

                datatable.DataTable(options);
            });
            return $$;
        }
    }
})();

$(function(){
    var shouldInit = null;
    if (datatableview.auto_initialize === undefined) {
        shouldInit = datatableview.autoInitialize;
    } else {
        shouldInit = datatableview.auto_initialize
    }

    if (shouldInit) {
        datatableview.initialize($('.datatable'));
    }
});
