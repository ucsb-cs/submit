String.prototype._format = function() {
    /* Taken from http://stackoverflow.com/a/4673436/176978 */
    var args = arguments;
    return this.replace(/{(\d+)}/g, function(match, number) {
    return typeof args[number] != 'undefined'
      ? args[number]
            : match
        ;
    });
};

function form_request(form, method, skip_empty) {
    if (typeof skip_empty == 'undefined' || skip_empty == null)
        skip_empty = false;
    var files_to_upload = [];

    var js_form = form2js(form, '.', skip_empty, function(node) {
        /* Find any file input fields and add them to the files array */
        if (!node.nodeName.match(/INPUT/i) || !node.type.match(/file/i))
            return false;
        if (node.files.length > 0 && !node.hasAttribute("disabled"))
            files_to_upload.push({name: node.name, files: node.files});
        return false;
    });

    file_handler = new FileHandler(files_to_upload, js_form, function() {
        /* Only submit the form once all files have replaced by file_ids */
        var jsonified_form = JSON.stringify(js_form);
        console.log('About to submit');
        console.log(js_form);
        $.ajax({url: form.action, data: jsonified_form, type: method,
                complete: handle_response, error: handle_error,
                contentType: "application/json; charset=utf-8",
                timeout: 30000});
    });
    return false;  // Ensure the form submission doesn't actually happen
}

function handle_error(xhr, status, error) {
    if (status == 'timeout')
        console.log('The request timed out.');
}

function handle_response(xhr) {
    if (xhr.status > 500) {
        console.log('Server error');
        console.log(xhr.responseText);
        return;
    }
    text = xhr.responseText;
    if (text == undefined) {
        console.log('Unexpected empty response body.')
        return;
    }
    data = JSON.parse(text);
    switch(xhr.status) {
    case 200:  // Ok
        if (data['redir_location'])
            window.location = data['redir_location'];
        else
            alert(data['message'])
        break;
    case 201:  // Created
        window.location = data['redir_location'];
        break;
    case 400:  // BadRequest
    case 403:  // Forbidden
    case 409:  // Conflict
        msg = data['error']
        if (typeof data['messages'] === 'string')
            msg += '\n * ' + data['messages']
        else
            for (i in data['messages'])
                msg += '\n * ' + data['messages'][i]
        alert(msg);
        break;
    case 410:  // Gone
        window.location = data['redir_location'];
        break;
    default:
        alert("Unhandled status code: " + xhr.status);
    }
}

function FileHandler(to_replace, js_form, completed_callback) {
    this.to_replace = to_replace;
    this.js_form = js_form;
    this.completed_callback = completed_callback;
    this.current = null;
    this.upload_or_submit();
}

FileHandler.prototype.upload_or_submit = function() {
    this.current = this.to_replace.pop();
    if (this.current)
        process_file(this);
    else
        this.completed_callback();
}

FileHandler.prototype.replace_file = function(xhr_response) {
    var file_id = $.parseJSON(xhr_response)['file_id'];
    this.js_form[this.current.name] = String(file_id);
    this.upload_or_submit();
}

function process_file(handler) {
    var file = handler.current.files[0];
    var reader = new FileReader();
    reader.onload = function(event) {  // When the file is loaded
        var data = event.target.result;
        setTimeout(function() {  // Perform asynchronously
            var base64 = window.btoa(data);
            var sha1 = hex_sha1(data);
            var url = '/file/' + sha1 + '/_';
            console.log('Checking if ' + sha1 + ' exists');
            $.ajax({url: url, type: 'INFO', complete: function(xhr) {
                // Test if file exists
                var submit = false;
                if (xhr.status == 200) {
                    submit = !$.parseJSON(xhr.responseText)['owns_file'];
                }
                if (submit || xhr.status == 403 || xhr.status == 404) {
                    console.log('Uploading file for ' + sha1);
                    var form_json = JSON.stringify({b64data: base64});
                    var url = '/file/' + sha1 + '/_';
                    $.ajax({url: url, type: 'PUT', complete: function(xhr) {
                        if (xhr.status == 200)
                            handler.replace_file(xhr.responseText);
                        else {
                            console.log('Error uploading file: ' + xhr.status);
                        }}, data: form_json});
                }
                else
                    handler.replace_file(xhr.responseText);
            }});
        }, 0);
    };
    reader.readAsBinaryString(file);
}


function UploadApp() {
    this.db = $('#dropbox');
    this.submit = $('#file_submit');
    this.all_files = {};
    this.current = null;
    this.target = null;
    var $this = this;

    $('#files').bind('change', function(e) {$this.add_file(e);});
    this.db.bind('drop', function(e) {$this.add_file(e);});
    this.db.bind('dragenter dragover dragleave', function(e) {
        e.stopPropagation();
        e.preventDefault();
        if (e.type == 'dragenter')
            e.target.className = 'drop-hover';
        else if (e.type == 'dragleave')
            e.target.className = '';
    });
    $('#upload_form').removeAttr('onsubmit').submit(function (e) {
        $this.submit_files(e);
    });
}

UploadApp.prototype.add_file = function(e) {
    e.stopPropagation();
    e.preventDefault();
    this.db.attr('class', '');
    var event = e.originalEvent;
    var files = event.target.files || event.dataTransfer.files;
    for (var i = 0; i < files.length; ++i) {
        if (files[i].size < 1024)
            var size = '{0} B'._format(files[i].size);
        else
            var size = '{0} KB'._format(Math.floor(files[i].size / 1024));
        var info = 'Name: {0} Size: {1}'._format(files[i].name, size);
        if (files[i].name in this.all_files)
            $('#pending_{0}'._format(files[i].name)).text(info);
        else
            $('<li id="pending_{0}">{1}</li>'._format(
                files[i].name, info)).appendTo('#pending');
        this.all_files[files[i].name] = files[i];
    }
    var num = Object.keys(this.all_files).length;
    this.submit.attr('disabled', num > 0 ? false : 'disabled');
    if (num == 1)
        this.submit.text('Submit ' + num + ' file');
    else
        this.submit.text('Submit ' + num + ' files');
}

UploadApp.prototype.replace_file = function(xhr_response) {
    var file_id = $.parseJSON(xhr_response)['file_id'];
    $('<input type="hidden" name="file_ids[]" value="{0}">'
      ._format(file_id)).appendTo('#upload_form');
    $('<input type="hidden" name="filenames[]" value="{0}">'
      ._format(this.current.name)).appendTo('#upload_form');
    this.upload_or_submit();
}

UploadApp.prototype.submit_files = function(e) {
    e.preventDefault();
    this.target = e.target;
    this.upload_or_submit();
}

UploadApp.prototype.upload_or_submit = function() {
    var keys = Object.keys(this.all_files);
    if (keys.length < 1)
        return form_request(this.target, 'put', true);
    var file = this.all_files[keys[0]]
    this.current = {name: file.name, files: [file]}
    delete this.all_files[keys[0]]
    process_file(this);
}
