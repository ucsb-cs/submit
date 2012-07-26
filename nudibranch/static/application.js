function form_request(form, method) {
    var jsonified_form = JSON.stringify(form2js(form, '.', false));
    var xhr = new XMLHttpRequest();
    xhr.open(method, form.action);
    xhr.onreadystatechange = function() {
        if (xhr.readyState == this.DONE) {
            data = JSON.parse(xhr.responseText);
            switch(xhr.status) {
            case 201:  // Created
                window.location = data['redir_location'];
                break;
            case 400:  // BadRequest
                msg = data['error']
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
    };
    xhr.send(jsonified_form);
    return false;  // Ensure the form submission doesn't actually happen
}
