"""Points d'entree de doot appeles par l'application Android."""

from doot import cli


def daemon() -> int:
    return cli.main([])


def once(args=None) -> int:
    """Un doot tout de suite, ou ce que demandent `args` (`--play rickroll`...)."""
    return cli.main([str(a) for a in args] if args else ["--once", "--ignore-season"])
