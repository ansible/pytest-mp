import pytest


conftest = """

    from time import time

    import pytest

    _mp_configure_hook_called_time = 0
    _mp_prefork_hook_called_time = 0
    _configure_hook_called_time = 0
    _generate_tests_hook_called_time = 0
    _clique_options = None
    _clique_id = -1


    @pytest.fixture(scope="function")
    def mp_configure_hook_called_time():
        return _mp_configure_hook_called_time

    @pytest.fixture(scope="function")
    def mp_prefork_hook_called_time():
        return _mp_prefork_hook_called_time

    @pytest.fixture(scope="function")
    def configure_hook_called_time():
        return _configure_hook_called_time

    @pytest.fixture(scope="function")
    def generate_tests_hook_called_time():
        return _generate_tests_hook_called_time

    @pytest.fixture(scope="function")
    def clique_options():
        return _clique_options

    @pytest.fixture(scope="function")
    def clique_id():
        return _clique_id

    def pytest_mp_configure(clique_options):
        global _mp_configure_hook_called_time, _clique_options
        _mp_configure_hook_called_time = time()
        _clique_options = clique_options

    def pytest_mp_prefork(clique_id):
        global _mp_prefork_hook_called_time, _clique_id
        _mp_prefork_hook_called_time = time()
        _clique_id = clique_id

    def pytest_configure(config):
        global _configure_hook_called_time
        _configure_hook_called_time = time()

    def pytest_generate_tests(metafunc):
        global _generate_tests_hook_called_time
        if _generate_tests_hook_called_time == 0:
            _generate_tests_hook_called_time = time()

    """


@pytest.mark.parametrize('clique_num', (0, 1, 10))
def test_pytest_mp_configure(testdir, clique_num):
    testdir.makeconftest(conftest)
    testdir.makepyfile("""

    def test_one(mp_configure_hook_called_time, clique_options, mp_clique_options):
        assert mp_configure_hook_called_time > 0
        assert len(clique_options) == {}
        assert clique_options == mp_clique_options
        for i in range(len(clique_options)):
            assert clique_options[i].num_processes == i+1

    """.format(clique_num))

    result = testdir.runpytest_subprocess('--mp', *['--mp-clique="--np={}"'.format(i + 1) for i in range(clique_num)])
    result.assert_outcomes(passed=1)
    assert result.ret == 0


def test_no_pytest_mp_configure_when_mp_disabled(testdir):
    testdir.makeconftest(conftest)
    testdir.makepyfile("""

    def test_one(mp_configure_hook_called_time, clique_options):
        assert mp_configure_hook_called_time == 0
        assert clique_options is None

    """)

    result = testdir.runpytest_subprocess('--mp-clique="--np=1"')
    result.assert_outcomes(passed=1)
    assert result.ret == 0


def test_pytest_mp_configure_after_pytest_configure(testdir):
    testdir.makeconftest(conftest)
    testdir.makepyfile("""

    def test_one(mp_configure_hook_called_time, configure_hook_called_time):
        assert configure_hook_called_time > 0
        assert mp_configure_hook_called_time > configure_hook_called_time

    """)

    result = testdir.runpytest_subprocess('--mp', '--mp-clique="--np=1"')
    result.assert_outcomes(passed=1)
    assert result.ret == 0


def test_pytest_mp_configure_before_pytest_generate_tests(testdir):
    testdir.makeconftest(conftest)
    testdir.makepyfile("""

    def test_one(mp_configure_hook_called_time, generate_tests_hook_called_time):
        assert mp_configure_hook_called_time > 0
        assert generate_tests_hook_called_time > mp_configure_hook_called_time

    """)


@pytest.mark.parametrize('clique_num', (1, 2, 4))
def test_pytest_mp_prefork(testdir, clique_num):
    testdir.makeconftest(conftest)
    testdir.makepyfile("""

    import pytest

    @pytest.mark.parametrize('count', range(10))
    def test_one(mp_prefork_hook_called_time, clique_id, mp_clique_id, mp_num_processes, count):
        assert mp_prefork_hook_called_time > 0
        assert mp_num_processes == 2
        assert clique_id == mp_clique_id

    """)

    result = testdir.runpytest_subprocess('--mp', '--np=2', *['--mp-clique=--np=4' for i in range(clique_num)])
    result.assert_outcomes(passed=10)
    assert result.ret == 0


def test_no_pytest_mp_prefork_when_no_clique(testdir):
    testdir.makeconftest(conftest)
    testdir.makepyfile("""

    def test_one(mp_prefork_hook_called_time, clique_id):
        assert mp_prefork_hook_called_time == 0
        assert clique_id == -1

    """)

    result = testdir.runpytest_subprocess('--mp')
    result.assert_outcomes(passed=1)
    assert result.ret == 0
