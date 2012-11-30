$(function(){
    var options_name_map = {
        'sortable': 'bSortable'
    };
    
    $('.datatable').each(function(){
        var datatable = $(this);
        var column_options = [];
        
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
                    
                    if (/^b[A-Z]/.test(name)) {
                        value = (value === 'true');
                    }
                    
                    options[name] = value;
                }
            }
            column_options.push(options);
        });
        
        var initialized_datatable = datatable.dataTable({
            "bServerSide": true,
            "bStateSave": true,
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
        });
        
        try {
            initialized_datatable.fnSetFilteringDelay();
        } catch (e) {
            console.info("datatable plugin fnSetFilteringDelay not available");
        }
    });
});
