function form_request(form, method) {
    var jsonified_form = JSON.stringify(form2js(form, '.', false));
    var xhr = new XMLHttpRequest();
    xhr.open(method, form.action);
    xhr.onreadystatechange = function() {
        if (xhr.readyState == this.DONE) {
            alert(xhr.status);
        }
    };
    xhr.send(jsonified_form);
    return false;  // Ensure the form submission doesn't actually happen
}
