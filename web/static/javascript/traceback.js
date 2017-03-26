function hide_traceback_text(traceback_button){
    payload = {
        traceback_text: traceback_button.value
    };
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


function restore_all(){
    payload = {};
    $.ajax({
        type: "POST",
        url: "/restore_all",
        data: JSON.stringify(payload),
        success: function() {
            location.reload();
        },
        contentType: "application/json"
    });
}
