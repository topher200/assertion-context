import logging

import click

from badcorp.util.setup_logging import setup_logging


logger = logging.getLogger()

LOG_FILE_LOCATION = '/tmp/badcorp.log'


@click.command()
def main():
    from badcorp.main import generate_assertions

    setup_logging(LOG_FILE_LOCATION)

    logger.debug('running BadCorp')
    generate_assertions()
    logger.debug('completed BadCorp')

if __name__ == '__main__':
    main()
