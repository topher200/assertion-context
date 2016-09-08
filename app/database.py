import psycopg2


DATABASE_NAME = u'assertion_context'
TABLE_NAME = u'asserts'


def connect_to_db():
    """
        Connects to database and creates a cursor.

        Returns a 2-tuple of the connection and the cursor.

        The cursor should be finalized with a `.commit()` or `.rollback()`. The, both the
        connection and the cursor should be closed with `.close()`.
    """
    conn = psycopg2.connect("dbname=%s user=%s" % (DATABASE_NAME, "postgres"))
    return (conn, conn.cursor())


def create_table():
    """
        Creates our database table if needed. Does nothing if it already exists
    """
    conn, cursor = connect_to_db()
    cursor.execute(
        ("CREATE TABLE %s ("
         "id serial PRIMARY KEY,"
         "parsed_log_message text,"
         "raw_log_message text,"
         "datetime text,"  # TODO not text
         "papertrail_id integer,"
         "origin_papertrail_id integer,"
         "line_number integer,"
         "instance_id text,"
         "program_name text,"
         ");"
        ), (DATABASE_NAME, )
    )
    cursor.commit()
    cursor.close()
    conn.close()


def save_logline(logline):
    conn, cursor = connect_to_db()
    cursor.execute(("INSERT INTO %s ("
                    "parsed_log_message,"
                    "raw_log_message,"
                    "datetime,"
                    "papertrail_id,"
                    "origin_papertrail_id,"
                    "line_number,"
                    "instance_id,"
                    "program_name,"
                    ") VALUES ("
                    "%s, "
    ))
