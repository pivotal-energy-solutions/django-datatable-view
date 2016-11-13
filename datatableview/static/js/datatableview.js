/* For datatable view */

var datatableview = {
    auto_initialize: false,
    defaults: {
        "serverSide": true,
        "paging": true
    },
    
    make_xeditable: function(options) {
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
        }
        return function(nRow, mData, iDisplayIndex) {
            $('td a[data-xeditable]', nRow).editable(options);
            return nRow;
        }
    },
    
    
    make_selectize: function(options) {
        var options = $.extend({}, options);
        if (!options.ajaxOptions) {
        	options.ajaxOptions = {}
        }
        if (!options.ajaxOptions.headers) {
        	options.ajaxOptions.headers = {}
        }
        /* Set CSRF in order to send post request safely in Django */
        options.ajaxOptions.headers['X-CSRFToken'] = datatableview.getCookie('csrftoken');
        
        /* We return the function that will selectize the correspondent elements */
        return function(nRow, mData, iDisplayIndex) {
        	/* We selectize al the elements inside "td" with a "data-selectize" attribute */
            $('td [data-selectize]', nRow).each(function(index, el) {
            	var selectizeOptions = $.extend({}, options);
            	
            	// We parse attributes in order to set appropriate options for selectize component
            	datatableview._selectizeAttributes(el, selectizeOptions);
            	
            	// Instead of xeditable, here we have to change our values manually. 
            	// So we perform an AJAX request when selectize element changes his value.
            	selectizeOptions['onChange'] = function(value) {
            		if (value) {
            			// Get values to send as form data
            			var serializedData = $(el).serializeArray();
            			serializedData[0].pk = $(el).attr("data-pk");
            			// Send values via ajax
            			$.ajax($.extend({
            				url: $(el).attr("data-url"),
            				type: "POST",
            				data: 	serializedData[0],
            			}, options.ajaxOptions));
            		}
                	
            	}
	            $(el).selectize(selectizeOptions);

            });

            return nRow;
        }
    },
    
    acceptedFunctions: ["load", "score", "render"],
    /* Set selectize options from html element attributes
     */
    _selectizeAttributes: function(el, selectizeOptions) {
    	var attributes = $(el)[0].attributes;
    	$.each( attributes, function( index, attr ) {
    		if (attr.name.startsWith("selectize-")) {
    			var selectizeKey = attr.name.replace("selectize-", "");
    			selectizeKey = selectizeKey.replace(/-([a-z])/g, function (m, w) {
    			    return w.toUpperCase();
    			});
    			// Cast string value into respective value
    			var value = $.isNumeric(attr.value) ? parseInt(attr.value) : attr.value;
    			value = (value == "True") ? true : value;
    			value = (value == "False") ? false : value;
    			
    			if (datatableview.acceptedFunctions.includes(selectizeKey)) {
    				value = eval(value);
    				if (value == undefined) {
    					console.warn("Function not defined: " + attr.value);
    				}
    			}
    			selectizeOptions[selectizeKey] = value;
    		}
        } );
    },

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
        var options_name_map = {
            'name': 'name',
            'config-sortable': 'orderable',
            'config-sorting': 'order',
            'config-visible': 'visible',
            'config-searchable': 'searchable'
        };

        var template_clear_button = $('<a href="#" class="clear-search">Clear</a>');

        var initialized_datatables = [];
        $$.each(function(){
            var datatable = $(this);
            var column_options = [];
            var sorting_options = [];

            datatable.find('thead th').each(function(){
                var header = $(this);
                var options = {};
                for (var i = 0; i < header[0].attributes.length; i++) {
                    var attr = header[0].attributes[i];
                    if (attr.specified && /^data-/.test(attr.name)) {
                        var name = attr.name.replace(/^data-/, '');
                        var value = attr.value;

                        // Typecasting out of string
                        name = options_name_map[name];
                        if (/^b/.test(name)) {
                            value = (value === 'true');
                        }

                        if (name == 'order') {
                            // This doesn't go in the column_options
                            var sort_info = value.split(',');
                            sort_info[1] = parseInt(sort_info[1]);
                            sorting_options.push(sort_info);
                            continue;
                        }

                        options[name] = value;
                    }
                }
                column_options.push(options);
            });

            // Arrange the sorting column requests and strip the priority information
            sorting_options.sort(function(a, b){ return a[0] - b[0] });
            for (var i = 0; i < sorting_options.length; i++) {
                sorting_options[i] = sorting_options[i].slice(1);
            }

            options = $.extend({}, datatableview.defaults, opts, {
                "order": sorting_options,
                "columns": column_options,
                "ajax": datatable.attr('data-source-url'),
                "pageLength": datatable.attr('data-page-length'),
                "infoCallback": function(oSettings, iStart, iEnd, iMax, iTotal, sPre){
                    $("#" + datatable.attr('data-result-counter-id')).html(parseInt(iTotal).toLocaleString());
                    var infoString = oSettings.oLanguage.sInfo.replace('_START_',iStart).replace('_END_',iEnd).replace('_TOTAL_',iTotal);
                    if (iMax != iTotal) {
                        infoString += oSettings.oLanguage.sInfoFiltered.replace('_MAX_',iMax);
                    }
                    // /******************************************************************
                    //  * ##########       ###       ######         ###
                    //  * ##########     ###  ##     ###   ##     ###  ##
                    //  *    ###        ###   ###    ###   ##    ###   ###
                    //  *    ###        ###   ###    ###   ##    ###   ###
                    //  *    ###        ###   ###    ###   ##    ###   ###
                    //  *    ###         ######      ######       ######
                    //  * ===============================================================
                    //  * The string at the bottom of the table showing entries being
                    //  * looked at is always updated, but not always rendered in all
                    //  * browsers *cough cough* Chrome, Safari.
                    //  * This makes it so that results string always updates.
                    //  *****************************************************************/
                    // var n = oSettings.aanFeatures.i;
                    // for (var i = 0, iLen = n.length; i < j; i++) {
                    //     $(n[i]).empty();
                    // }
                    return infoString;
                }
            });
            try {
                options = confirm_datatable_options(options, datatable);
            } catch (e) {

            }

            var initialized_datatable = datatable.dataTable(options);
            initialized_datatables.push(initialized_datatable[0]);

            try {
                initialized_datatable.fnSetFilteringDelay();
            } catch (e) {
                console.info("datatable plugin fnSetFilteringDelay not available");
            }

            var search_input = initialized_datatable.closest('.dataTables_wrapper').find('.dataTables_filter input');
            var clear_button = template_clear_button.clone().click(function(){
                $(this).trigger('clear.datatable', [initialized_datatable]);
                return false;
            }).bind('clear.datatable', function(){
                search_input.val('').keyup();
            });
            search_input.after(clear_button).after(' ');
        });
        return $(initialized_datatables).dataTable();
    }
}

$(function(){
    if (datatableview.auto_initialize) {
        datatableview.initialize($('.datatable'));
    }
});
