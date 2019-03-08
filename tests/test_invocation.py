import pytest
import psutil

cpu_count = psutil.cpu_count()


def test_confirm_options_in_help(testdir):
    result = testdir.runpytest('--help')
    result.stdout.fnmatch_lines(['pytest-mp:', '*--mp, --multiprocessing',
                                 '*--np=NUM_PROCESSES, --num-processes=NUM_PROCESSES'])


def _parametrized_ini():
    header = "[pytest]\n"
    mp = "mp = {}\n"
    np = "num_processes = {}\n"
    return [(header + mp.format(False), False, None),
            (header + mp.format(False) + np.format(100), False, 100),
            (header + np.format(0), False, 0),
            (header + np.format(100), False, 100),
            (header + mp.format(True), True, None),
            (header + mp.format(True) + np.format(100), True, 100)]


@pytest.mark.parametrize('ini_content, mp, num_processes', _parametrized_ini())
def test_ini_without_cmdline(testdir, ini_content, mp, num_processes):
    """Confirms that .ini values are used to determine mp run options"""
    testdir.makeini(ini_content)

    if mp:
        if num_processes != 0:
            num_processes = num_processes or cpu_count
    else:
        num_processes = 0

    testdir.makepyfile("""
        import pytest
        import time

        def test_mp(mp_use_mp):  # mp_use_mp is pytest-mp helper fixture
            assert mp_use_mp == {}

        def test_num_processes(mp_num_processes):  # mp_num_processes is pytest-mp helper fixture
            assert mp_num_processes == {}

    """.format(mp, num_processes))

    result = testdir.runpytest()
    result.stdout.re_match_lines(['.*2 passed.*in.*seconds.*'])
    assert result.ret == 0


@pytest.mark.parametrize('cmd_mp, cmd_num_processes',
                         [(True, None), (True, 50), (True, 0), (False, None), (False, 50), (False, 0)])
@pytest.mark.parametrize('ini_content, ini_mp, ini_num_processes', _parametrized_ini())
def test_ini_with_cmdline(testdir, cmd_mp, cmd_num_processes, ini_content, ini_mp, ini_num_processes):
    """Confirms that .ini values are not used when cmdline values are specified to determine mp run options"""
    testdir.makeini(ini_content)

    use_mp = cmd_mp or ini_mp
    if use_mp:
        if cmd_num_processes == 0:
            num_processes = cmd_num_processes
        else:
            priority = cmd_num_processes or ini_num_processes
            num_processes = cpu_count if priority is None else priority
    else:
        num_processes = 0

    testdir.makepyfile("""
        import pytest
        import time

        def test_mp(mp_use_mp):
            assert mp_use_mp == {}

        def test_num_processes(mp_num_processes):
            assert mp_num_processes == {}

    """.format(use_mp, num_processes))

    cmd_options = []
    if cmd_mp:
        cmd_options.append('--mp')
    if cmd_num_processes is not None:
        cmd_options.append('--num-processes={}'.format(cmd_num_processes))

    result = testdir.runpytest(*cmd_options)

    result.stdout.re_match_lines(['.*2 passed.*in.*seconds.*'])
    assert result.ret == 0
