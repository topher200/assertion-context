import click
from dotenv import load_dotenv


@click.command()
@click.argument('config_file')
def main(config_file=None):
    load_dotenv(config_file)

    # load config file before doing imports
    from badcorp.main import generate_assertions

    generate_assertions()

if __name__ == '__main__':
    main()
