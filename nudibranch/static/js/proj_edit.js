function hfd(lhs, rhs) {
    var retval = $('<div>');
    var control = $('<div class="control-label">');
    if (lhs != '') {
        $(lhs).appendTo(control);
        control.appendTo(retval);
    }
    var group = $('<div class="controls">');
    $(rhs).appendTo(group);
    group.appendTo(retval);
    return retval;
}
function files_form(category, info, ids, unique) {
    var lcn = null;
    var new_title = '<i class="icon-white icon-file"></i> New';
    if (category == 0) {
        var name = 'Build File';
        var path = build_file_path;
    }
    else if (category == 1) {
        var name = 'Execution File';
        var path = execution_file_path;
    }
    else {
        var name = 'Expected File';
        var path = expected_file_path;
        lcn = 'file_verifier';
        new_title = '<i class="icon-white icon-list"></i> Define'
    }
    lcn = lcn || name.replace(' ', '_').toLowerCase();
    var retval = $('<div class="pull-left well well-small"><h3>Select {0}s\
</h3>'._format(name));
    var cb_class = 'cb_{0}_{1}'._format(unique, category);
    $('<p>(<a onclick="$(\'.' + cb_class + '\').prop(\'checked\', true);">Select All</a>) |\
(<a onclick="$(\'.' + cb_class + '\').prop(\'checked\', false);">Select None</a>)</p>'._format(cb_class)).appendTo(retval);
    for (var i = 0; i < info.length; ++i) {
        var f = info[i];
        var checked = $.inArray(f['id'], ids) != -1 ? 'checked="checked"' : '';

        var lhs = '<span class="btn btn-danger btn-mini button-delete" \
data-name="{0}" data-url="{1}/{2}"><i class="icon-white icon-trash"></i> \
Delete</span>'._format(f['name'], path, f['id']);;

        if (category != 2) {
            lhs += '<a class="btn btn-info btn-mini" style="color: white" \
href="{0}/{1}/{2}" target="_blank"><i class="icon-white icon-search"></i> \
View</a>'._format(file_path, f['file_hex'], f['name'])
        }
        else {
            lhs += '<span class="btn btn-warning btn-mini" onclick=\
"$(\'#file_verifier_{0}\').dialog(\'open\');"><i class="icon-white \
icon-pencil"></i> Edit</span>'._format(f['id']);
        }
        var rhs = '<label class="checkbox"><input type="checkbox" name="{0}_\
ids[]" value="{1}" class="{2}" {3}>  {4}</label>'._format(
                   lcn, f['id'], cb_class, checked, f['name']);
        var div = $('<div>');
        $('<div class="pull-left">').append($(lhs)).appendTo(div);
        $('<div class="pull-left" style="margin-left:5px">').append($(rhs))
            .appendTo(div);
        $('<div class="clearfix">').appendTo(div);
        div.appendTo(retval);
    }
    $('<div style="text-align: center">').append($('<span class="btn \
btn-success btn-mini" onclick="$(\'#{0}_new\').dialog(\'open\');">{1} {2}\
</span>'._format(lcn, new_title, name))).appendTo(retval);
    return retval;
}
function testable_div(info) {
    var div = $('<div id="testable_tab_{0}">'._format(info['id']));
    if (info['id'] == 'new') {
        var action = '/testable';
        var method = 'PUT';
        var tb_name = '';
    }
    else {
        var action = '/testable/{0}'._format(info['id']);
        var method = 'POST';
        var tb_name = info['name'];
    }
    var hidden = info['hidden'] ? 'checked="checked"' : '';
    var form = $(('<form class="form-horizontal" role="form" action="{0}"' +
                  ' onsubmit="return form_request(this, \'{1}\', true);"/>')
                 ._format(action, method));
    var row = $('<div class="row-fluid">');
    files_form(0, build_files, info['build_files'],
               info['id']).appendTo(row);
    files_form(1, execution_files, info['execution_files'],
               info['id']).appendTo(row);
    files_form(2, expected_files, info['expected_files'],
               info['id']).appendTo(row);
    row.appendTo(form);
    hfd('<label for="testable_name_{0}">Testable Name</label>'
        ._format(info['id']),
        '<input type="text" id="testable_name_{0}" name="name" value="{1}">'
        ._format(info['id'], tb_name)).appendTo(form);
    hfd('<label for="make_target_{0}">Make Target</label>'
        ._format(info['id']),
        ('<input type="text" id="make_target_{0}" name="make_target" ' +
         'placeholder="do not run make" value="{1}">')
        ._format(info['id'], info['target'] || '')).appendTo(form);
    hfd('<label for="executable_{0}">Executable</label>'
        ._format(info['id']),
        ('<input type="text" id="executable_{0}" name="executable" ' +
         'value="{1}">')._format(info['id'], info['executable']))
        .appendTo(form);
    hfd('',
        '<label class="checkbox"><input type="checkbox" name="is_hidden" ' +
        'value="1" {0}> Hide results from students</label>'._format(hidden))
        .appendTo(form);
    if (info['id'] == 'new') {
        $('<input type="hidden" name="project_id" value="{0}"/>'
          ._format(proj_id)).appendTo(form);
        $('<button class="btn btn-success" type="submit">Add Testable</button>'
         ).appendTo(form);
    }
    else {
        $('<button class="btn btn-warning" type="submit">Update {0}</button>\
<span class="btn btn-danger button-delete" data-name="{0}" \
data-url="/testable/{1}"><i class="icon-white icon-trash"></i> Delete \
{0}</span>'._format(info['name'], info['id'])).appendTo(form);
    }
    form.appendTo(div);
    $('<hr><h3>Test Cases <span class="btn btn-success" onclick="$(\'#testable\
_{0}_tc_new\').dialog(\'open\');"><i class="icon-white icon-fire"></i> New \
Test Case</span></h3>'._format(info['id'])).appendTo(div);
    var table = $('<table role="table" class="table table-condensed \
table-hover">');
    $('<thead><tr><th>Test Name</th><th>Info</th></tr></thead>')
        .appendTo(table);
    var body = $('<tbody>');
    for (var i = 0; i < info['test_cases'].length; ++i) {
        var data = info['test_cases'][i];
        var other = '<span class="badge">{0}</span>'._format(data['points']);
        var args = data['args'].split(/\s+/);
        if (args.length > 1)
            other += ('<span class="label label-success">{0} args</span>'
                      ._format(args.length));
        if (data['stdin'])
            other += '<span class="label label-info">stdin</span>'
        if (data['source'] != 'stdout')
            other += '<span class="label">{0}</span>'._format(data['source']);
        if (data['output_type'] != 'diff')
            other += '<span class="label label-inverse">{0}</span>'._format(
                data['output_type']);
        else if (data['hide_expected'])
            other += '<span class="label label-important">Hide Expected</span>'
        $('<tr><td><span class="btn btn-warning btn-mini" onclick="$(\'#update\
_tc_{0}\').dialog(\'open\');"><i class="icon-white icon-pencil"></i> Edit\
</span> {1}</td><td>{2}</td></tr>'
          ._format(data['id'], data['name'], other))
            .appendTo(body);
    }
    body.appendTo(table);
    table.appendTo(div);
    return div;
}
function add_testables(testable_data) {
    var tt = $("#testable_tab");
    var ul = tt.find('ul');
    for (var i = 0; i < testable_data.length; ++i) {
        var info = testable_data[i];
        ul.append('<li><a href="#testable_tab_{0}">{1}</a></li>'
                  ._format(info['id'], info['name']));
        testable_div(info).appendTo(tt);
    }
}
$(function() {
    add_testables(testables);

    $(".dialog").dialog({autoOpen: false, modal: true, width: 'auto'});
    $("#testable_tab").tabs();
    $(".button-delete").on("click", function(event) {
        var name = event.target.getAttribute("data-name");
        var url = event.target.getAttribute("data-url");
        if (confirm("Are you sure you want to delete " + name + "?")) {
            $.ajax({url: url, type: "delete", complete: handle_response});
        }
    });
    $(".toggle_tc_file").on("change", function(event) {
        var testable = event.target.getAttribute("data-testable");
        var tc = event.target.getAttribute("data-tc");
        var div = $("#testable_" + testable + "_" + tc + "_file_div");
        var input = $("#testable_" + testable + "_tc_output_filename_" + tc);
        if (event.target.value == "file") {
            div.show();
            input.removeAttr("disabled");
        }
        else {
            div.hide();
            input.attr("disabled", "disabled");
        }
    });
    $(".toggle_tc_expected").on("change", function(event) {
        var testable = event.target.getAttribute("data-testable");
        var tc = event.target.getAttribute("data-tc");
        var div = $("#testable_" + testable + "_" + tc + "_expected_div");
        var hidden = $("#testable_" + testable + "_tc_expected_id_" + tc);
        var input = $("#testable_" + testable + "_tc_expected_" + tc);
        if (event.target.value == "diff") {
            div.show();
            hidden.removeAttr("disabled");
            input.removeAttr("disabled");
        }
        else {
            div.hide();
            hidden.attr("disabled", "disabled");
            input.attr("disabled", "disabled");
        }
    });
    $("#requeue").on("click", function(event) {
        if (confirm("Are you sure you want to requeue all the latest submissions?")) {
            $.ajax({url: window.location.href, type: 'put', complete: handle_response});
        }
    });
});
