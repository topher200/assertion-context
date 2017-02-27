function hide_traceback_text(traceback_button){
    payload = {
        traceback_text: traceback_button.value
    };
    console.log("payload: ", payload);
    $.ajax({
        type: "POST",
        url: "/hide_traceback",
        data: JSON.stringify(payload),
        success: function() {
            location.reload();
        },
        contentType: "application/json"
    });
}
