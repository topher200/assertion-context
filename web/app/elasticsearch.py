from .logline import LogLine


def save_log_line(es, log_line):
    """
        Takes a L{LogLine} and saves it to the database

        es must be an instance of FlaskElasticsearch
    """
    assert isinstance(log_line, LogLine), (type(log_line), log_line)
    doc = log_line.document()
    es.index(
        index='logline-index',
        doc_type='logline',
        body=doc
    )
