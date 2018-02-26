function parse_date(date){
    var payload = {
        date: date
    };
    $.ajax({
        type: "POST",
        url: "/api/parse_s3_day",
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

function update_all_jira_tickets(){
    var payload = {
        all: true
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

function invalidate_cache(){
    var payload = {};
    $.ajax({
        type: "PUT",
        url: "/api/invalidate_cache",
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

function purge_celery_queue(){
    var payload = {};
    $.ajax({
        type: "PUT",
        url: "/api/purge_celery_queue",
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
