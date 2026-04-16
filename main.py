import click

@click.group()
def cli():
    pass

@cli.command()
def compare():
    pass

@cli.command()
def migrate():
    pass

@cli.command()
def validate():
    pass