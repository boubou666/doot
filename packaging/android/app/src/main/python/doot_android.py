"""Points d'entree de doot appeles par l'application Android."""

from doot import cli


def daemon() -> int:
    return cli.main([])


def once() -> int:
    return cli.main(["--once", "--ignore-season"])
