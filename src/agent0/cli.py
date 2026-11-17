import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def version() -> None:
    from importlib.metadata import version as v

    typer.echo(v("agent0"))
