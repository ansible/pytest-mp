import pytest
import psutil

cpu_count = psutil.cpu_count()


def test_plugin_loaded(testdir):
    testdir.makepyfile("""
        def test_one(pytestconfig):
            assert pytestconfig.pluginmanager.get_plugin('pytest-mp')
    """)
    result = testdir.runpytest_subprocess()
    result.assert_outcomes(passed=1)
    assert result.ret == 0


def test_confirm_options_in_help(testdir):
    result = testdir.runpytest_subprocess('--help')
    result.stdout.fnmatch_lines(['pytest-mp:', '*--mp, --multiprocessing',
                                 '*--np=NUM_PROCESSES, --num-processes=NUM_PROCESSES',
                                 '*--mp-clique=PYTEST_OPTIONS'])


def _parametrized_ini():
    header = "[pytest]\n"
    mp = "mp = {}\n"
    np = "num_processes = {}\n"
    mpc = "mp_cliques = {}\n"
    mpc_0 = mpc.format('')
    mpc_2 = mpc.format('--np=1 "--np 2"')
    return [(header + mp.format(False), False, None, []),
            (header + mp.format(False) + np.format(100) + mpc_2, False, 100, [1, 2]),
            (header + np.format(0) + mpc_0, False, 0, []),
            (header + np.format(100) + mpc_2, False, 100, [1, 2]),
            (header + mp.format(True), True, None, []),
            (header + mp.format(True) + np.format(100) + mpc_2, True, 100, [1, 2])]


@pytest.mark.parametrize('ini_content, mp, num_processes, clique_options', _parametrized_ini())
def test_ini_without_cmdline(testdir, ini_content, mp, num_processes, clique_options):
    """Confirms that .ini values are used to determine mp run options"""
    testdir.makeini(ini_content)

    if mp:
        if num_processes != 0:
            num_processes = num_processes or cpu_count
    else:
        num_processes = 0
        clique_options = []

    testdir.makepyfile("""
        import pytest
        import time

        def test_mp(mp_use_mp):  # mp_use_mp is pytest-mp helper fixture
            assert mp_use_mp == {}

        def test_num_processes(mp_num_processes):  # mp_num_processes is pytest-mp helper fixture
            assert mp_num_processes == {}

        def test_clique_options(mp_clique_options):  # mp_clique_options is pytest-mp helper fixture
            assert [o.num_processes for o in mp_clique_options] == {}

    """.format(mp, num_processes, clique_options))

    result = testdir.runpytest_subprocess()

    result.stdout.fnmatch_lines(['*= 3 passed in * seconds =*'])
    assert result.ret == 0


@pytest.mark.parametrize('cmd_mp, cmd_num_processes, cmd_clique_options',
                         [(True, None, []), (True, 50, [1, 2]), (True, 0, [1]),
                          (False, None, []), (False, 50, [1, 2]), (False, 0, [1])])
@pytest.mark.parametrize('ini_content, ini_mp, ini_num_processes, ini_clique_options', _parametrized_ini())
def test_ini_with_cmdline(testdir, cmd_mp, cmd_num_processes, cmd_clique_options,
                          ini_content, ini_mp, ini_num_processes, ini_clique_options):
    """Confirms that .ini values are not used when cmdline values are specified to determine mp run options"""
    testdir.makeini(ini_content)

    use_mp = cmd_mp or ini_mp
    if use_mp:
        if cmd_num_processes == 0:
            num_processes = cmd_num_processes
        else:
            priority = cmd_num_processes or ini_num_processes
            num_processes = cpu_count if priority is None else priority
        clique_options = cmd_clique_options or ini_clique_options
    else:
        num_processes = 0
        clique_options = []

    testdir.makepyfile("""
        import pytest
        import time

        def test_mp(mp_use_mp):
            assert mp_use_mp == {}

        def test_num_processes(mp_num_processes):
            assert mp_num_processes == {}

        def test_clique_options(mp_clique_options):
            assert [o.num_processes for o in mp_clique_options] == {}

    """.format(use_mp, num_processes, clique_options))

    cmd_options = []
    if cmd_mp:
        cmd_options.append('--mp')
    if cmd_num_processes is not None:
        cmd_options.append('--num-processes={}'.format(cmd_num_processes))
    for i in cmd_clique_options:
        cmd_options.append('--mp-clique=--np={} --log-level=DEBUG'.format(i))

    result = testdir.runpytest_subprocess(*cmd_options)

    result.stdout.fnmatch_lines(['*= 3 passed in * seconds =*'])
    assert result.ret == 0
