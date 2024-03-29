/* For datatable view */

var datatableview = (function(){
    var defaultDataTableOptions = {
        "serverSide": true,
        "paging": true
    }
    var optionsNameMap = {
        'name': 'name',
        'config-sortable': 'orderable',
        'config-sorting': 'order',
        'config-visible': 'visible',
        'config-searchable': 'searchable'
    };

    var checkGlobalConfirmHook = true;
    var autoInitialize = false;

    function initialize($$, opts) {
        $$.each(function(){
            var datatable = $(this);
            var options = datatableview.getOptions(datatable, opts);
            datatable.DataTable(options);
        });
        return $$;
    }

    function getOptions(datatable, opts) {
        /* Reads the options found on the datatable DOM into an object ready to be sent to the
           actual DataTable() constructor.  Is also responsible for calling the finalizeOptions()
           hook to process what is found.
        */
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
                    if (/^(true|false)/.test(value.toLowerCase())) {
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
                var infoString;
                if (iTotal == 0) {
                    infoString = oSettings.oLanguage.sInfoEmpty.replace('_START_',iStart).replace('_END_',iEnd).replace('_TOTAL_',iTotal);
                }
                else {
                    infoString = oSettings.oLanguage.sInfo.replace('_START_',iStart).replace('_END_',iEnd).replace('_TOTAL_',iTotal);
                    if (iMax != iTotal) {
                        infoString += oSettings.oLanguage.sInfoFiltered.replace('_MAX_',iMax);
                    }
                }

                return infoString;
            }
        });
        options.ajax = $.extend(options.ajax, {
            "url": datatable.attr('data-source-url'),
            "type": datatable.attr('data-ajax-method') || 'GET',
            "beforeSend": function(request){
                request.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
            }
        });

        options = datatableview.finalizeOptions(datatable, options);
        return options;
    }

    function finalizeOptions(datatable, options) {
        /* Hook for processing all options before sent to actual DataTable() constructor. */

        // Legacy behavior, will be removed in favor of user providing their own finalizeOptions()
        if (datatableview.checkGlobalConfirmHook) {
            if (window.confirm_datatable_options !== undefined) {
                options = window.confirm_datatable_options(options, datatable);
            }
        }
        return options;
    }

    function makeXEditable(options) {
        var options = $.extend({}, options);
        if (!options.ajaxOptions) {
            options.ajaxOptions = {}
        }
        if (!options.ajaxOptions.headers) {
            options.ajaxOptions.headers = {}
        }
        options.ajaxOptions.headers['X-CSRFToken'] = getCookie('csrftoken');
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
    }

    function getCookie(name) {
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
    }

    var api = {
        // values
        autoInitialize: autoInitialize,
        auto_initialize: undefined,  // Legacy name
        checkGlobalConfirmHook: checkGlobalConfirmHook,
        defaults: defaultDataTableOptions,

        // functions
        initialize: initialize,
        getOptions: getOptions,
        finalizeOptions: finalizeOptions,
        makeXEditable: makeXEditable,
        make_xeditable: makeXEditable  // Legacy name
    }
    return api;
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
