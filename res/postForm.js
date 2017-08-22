function post(path, params, method) {
    method = method || "post"; // Set method to post by default if not specified.

    // The rest of this code assumes you are not using a library.
    // It can be made less wordy if you use one.
    var form = document.createElement("form");
    form.setAttribute("method", method);
    form.setAttribute("action", path);
	
	for(var i = 0; i < params.length; i++) {
		var param = params[i]
		var hiddenField = document.createElement("input");
            hiddenField.setAttribute("type", "hidden");
            hiddenField.setAttribute("name", param[0]);
            hiddenField.setAttribute("value", param[1]);
            form.appendChild(hiddenField);
	}

    document.body.appendChild(form);
    form.submit();
}