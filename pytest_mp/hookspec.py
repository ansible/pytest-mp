from pluggy import HookspecMarker


hookspec = HookspecMarker("pytest")


@hookspec
def pytest_mp_configure(clique_options):
    """
    Allows plugins and conftest files to perform initial clique configuration.

    This hook is called for every plugin and conftest file after command line options of cliques have been parsed.

    :param list[argparse.Namespace] clique_options: list of options of cliques; empty if no clique explicitly created.
    """


@hookspec
def pytest_mp_prefork(clique_id):
    """
    Allows plugins and conftest files to perform configuration for a specific clique before forking a new process.

    This hook is called for every plugin and conftest file before forking a new process.

    :param int clique_id: the clique id starting from 0.
    """
