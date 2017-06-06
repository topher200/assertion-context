function update_jira_db(issue_key){
    var payload = {
        issue_key: issue_key
    };
    $.ajax({
        type: "PUT",
        url: "/api/update_jira_db",
        data: JSON.stringify(payload),
        success: function() {
            location.reload();
        },
        error: function() {
            location.reload();
        },
        contentType: "application/json"
    });
}

