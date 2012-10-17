function handle_response(xhr) {
    data = JSON.parse(xhr.responseText);
    switch(xhr.status) {
    case 200:  // Ok
        alert(data['message'])
        break;
    case 201:  // Created
        window.location = data['redir_location'];
        break;
    case 400:  // BadRequest
        msg = data['error']
        if (typeof data['messages'] === 'string')
            msg += '\n' + data['messages']
        else
            for (i in data['messages'])
                msg += '\n' + data['messages'][i]
        alert(msg);
        break;
    case 409:  // Conflict
        alert(data['message']);
        break;
        case 410:  // Gone
        window.location = data['redir_location'];
        break;
    default:
        alert("Unhandled status code: " + xhr.status);
    }
}

function form_request(form, method, skip_empty) {
    if (typeof skip_empty == 'undefined' || skip_empty == null)
        skip_empty = false;
    var jsonified_form = JSON.stringify(form2js(form, '.', skip_empty));
    $.ajax({url: form.action, data: jsonified_form, type: method,
            complete: handle_response});
    return false;  // Ensure the form submission doesn't actually happen
}

function FileToUpload(file, input) {
    this.file = file;
    this.input = input;
    this.sha1 = this.base64 = null;
}

FileToUpload.prototype.associate_makefile = function(response) {
    var data = $.parseJSON(response);
    $('#makefile_id')[0].value = data['file_id'];
    $('#project_form').submit();
}

FileToUpload.prototype.calculate_sha1 = function(data) {
    this.base64 = window.btoa(data);
    this.sha1 = hex_sha1(data);
    // Test to see if the file has already been uploaded
    var url = this.input.form.action.replace('_REPLACE_', this.sha1);
    this.input.form.action = url;
    var $this = this;
    $.ajax({url: url, complete: function(xhr) {$this.check_for_file(xhr);}});
}

FileToUpload.prototype.check_for_file = function(xhr) {
    var status = xhr.status;
    if (status == 404) {
        var el = document.createElement('input');
        el.type = el.value = 'submit';
    }
    else {
        this.associate_makefile(xhr.responseText);
        var el = document.createElement('span')
        el.innerHTML = 'file already uploaded';
    }
    this.input.parentNode.insertBefore(el, this.input.nextSibling);
    var $this = this;
    this.input.form.onsubmit = function() {return $this.upload();};
}

FileToUpload.prototype.handle_upload = function(xhr) {
    var status = xhr.status;
    if (status == 200) {
        this.associate_makefile(xhr.responseText);
    }
    else {
        alert('Error uploading file: ' + xhr.status);
    }
}

FileToUpload.prototype.on_file_load = function(event) {
    var $this = this;
    setTimeout(function(){$this.calculate_sha1(event.target.result)}, 0);
}

FileToUpload.prototype.process = function() {
    var reader = new FileReader();
    var $this = this;
    reader.onload = function(event){$this.on_file_load(event);};
    reader.readAsBinaryString(this.file);
}

FileToUpload.prototype.upload = function() {
    jsonified_form = JSON.stringify({b64data: this.base64});
    var $this = this;
    $.ajax({url: this.input.form.action, data: jsonified_form, type: 'PUT',
            complete: function(xhr) {$this.handle_upload(xhr);}});
    return false;
}

function file_select_handler(event) {
    var files = event.target.files || event.dataTransfer.files;
    var input = event.target;
    for (var i = 0; i < files.length; ++i) {
        var to_upload = new FileToUpload(files[i], input);
        to_upload.process();
    }
}


function initialize() {
    $('.uploader input[type=file]').change(file_select_handler);
}

$(document).ready(function() {
    initialize();
});
