$(function(){
    $('.datatable').each(function(){
        var datatable = $(this);
        var column_options = [];
        
        datatable.find('th').each(function(){
            var header = $(this);
            var options = {};
            for (var i = 0; i < header[0].attributes.length; i++) {
                var attr = header[i];
                if (attr.specified && /^data-/.test(attr.name)) {
                    var name = attr.name.replace(/^data-/, '');
                    var value = attr.value;
                    
                    // Typecasting out of string
                    if (/^b[A-Z]/.test(name)) {
                        value = (value === 'true');
                    }
                    
                    options[name] = value;
                    console.log(attr.name + ": " + attr.value);
                }
            }
            column_options.push(options);
        });
        
        datatable.dataTable({
            "bServerSide": true,
            "aoColumns": column_options,
            "sAjaxSource": datatable.attr('data-source-url'),
            "fnInfoCallback": function(oSettings, iStart, iEnd, iMax, iTotal, sPre){
                $("#id_count").html(iTotal);
                return "Showing "+iStart +" to "+ iEnd+" of "+iTotal+" entries";
            }
        });
    });
});
