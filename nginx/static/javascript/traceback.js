function hide_traceback_text(traceback_button){
    var payload = {
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


function create_jira_ticket(traceback_button){
    traceback_button.disabled = true;  // disable button during processing
    var payload = {
        origin_papertrail_id: traceback_button.value
    };
    $.ajax({
        type: "POST",
        url: "/create_jira_ticket",
        data: JSON.stringify(payload),
        success: function(textStatus) {
            traceback_button.disabled = false;
            toastr.info(textStatus);
        },
        error: function(textStatus, errorThrown) {
            traceback_button.disabled = false;
            toastr.error("Server error while trying to create jira ticket");
        },
        contentType: "application/json"
    });
}

function jira_comment(comment_button, issue_key, origin_papertrail_id) {
    comment_button.disabled = true;  // disable button during processing
    var payload = {
        origin_papertrail_id: origin_papertrail_id,
        issue_key: issue_key
    };
    $.ajax({
        type: "POST",
        url: "/jira_comment",
        data: JSON.stringify(payload),
        success: function(textStatus) {
            comment_button.disabled = false;
            toastr.info(textStatus);
        },
        error: function(textStatus, errorThrown) {
            comment_button.disabled = false;
            toastr.error("Server error while trying to create comment on " + issue_key);
        },
        contentType: "application/json"
    });
}
