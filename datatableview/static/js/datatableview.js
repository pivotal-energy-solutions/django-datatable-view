function confirm_datatable_options(options, datatable) {
    return options;
}

$(function(){
    var options_name_map = {
        'sortable': 'bSortable',
        'sorting': 'aaSorting'
    };
    
    var template_clear_button = $('<a href="#" class="clear-search">Clear</a>');
    
    $('.datatable').each(function(){
        var datatable = $(this);
        var column_options = [];
        var sorting_options = [];
        
        datatable.find('th').each(function(){
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
                    
                    if (name == 'aaSorting') {
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
        
        options = {
            "bServerSide": true,
            "bStateSave": true,
            "aaSorting": sorting_options,
            "aoColumns": column_options,
            "sAjaxSource": datatable.attr('data-source-url'),
            "fnInfoCallback": function(oSettings, iStart, iEnd, iMax, iTotal, sPre){
                $("#id_count").html(iTotal); // # TODO: Find this dynamically instead of by hard ID
                var infoString = "Showing "+iStart +" to "+ iEnd+" of "+iTotal+" entries";
                if (iMax != iTotal) {
                    infoString +=  " (filtered from "+iMax+" total entries)";
                }
                return infoString;
            }
        }
        try {
            options = confirm_datatable_options(options, datatable);
        } catch (e) {
            
        }
        
        var initialized_datatable = datatable.dataTable(options);
        
        try {
            initialized_datatable.fnSetFilteringDelay();
        } catch (e) {
            console.info("datatable plugin fnSetFilteringDelay not available");
        }
        
        var search_input = initialized_datatable.closest('.dataTables_wrapper').find('.dataTables_filter input');
        var clear_button = template_clear_button.clone().click(function(){
            search_input.val('').keyup();
            return false;
        });
        search_input.after(clear_button).after(' ');
    });
});
