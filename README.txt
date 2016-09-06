Determine the cause of an assertion error found in Papertrail logs

Takes the archived Papertrail logs in .tsv.gz format. Unzips them. Searches them
for any errors. When an error is found, we go backwards in the logs to find the
root cause (context) of the assertion, definied by "the contents of the lines of
the traceback previous to the assertion happening." We do this by determining
the instance ID of the machine that had the assertion and searching the logs for
the lines on that machine previous to the offending line.


## Files
- app/main.py: CLI and HTTP API entrypoints into this app
- app/file_parser.py: the powerhouse that does our log file processing. has extensive docs!
