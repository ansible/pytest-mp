import pytest


def test_unknown_strategy_forbidden(testdir):
    testdir.makepyfile("""
        import pytest

        @pytest.mark.mp_group(group='TestGroup', strategy='unknown')
        @pytest.mark.parametrize('val', range(1, 6))
        def test_two(val):
            assert True

    """)

    result = testdir.runpytest_subprocess('--mp')
    result.stdout.fnmatch_lines(['*Exception: Unknown strategy unknown',
                                 '*= no tests ran in * seconds =*'])
    assert result.ret == 3


def test_conflicting_strategy_forbidden(testdir):
    testdir.makepyfile("""
        import pytest

        @pytest.mark.mp_group('TestGroup')
        @pytest.mark.parametrize('val', range(1, 6))
        def test_one(val):
            assert val


        @pytest.mark.mp_group(group='TestGroup', strategy='serial')
        @pytest.mark.parametrize('val', range(1, 6))
        def test_two(val):
            assert True

    """)

    result = testdir.runpytest_subprocess('--mp')
    result.stdout.fnmatch_lines(['*Exception: TestGroup already has specified strategy free.',
                                 '*= no tests ran in * seconds =*'])
    assert result.ret == 3


def test_free(testdir):
    """Confirms that there is no shared state in any test running free strategy
    """
    testdir.makepyfile("""
        import pytest

        shared_state = dict()  # Should always be empty w/ free

        @pytest.mark.mp_group('TestGroup', 'free')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_one(val):
            assert not shared_state
            shared_state['test_one_destructive'] = True
            shared_state['all_destructive'] = True


        @pytest.mark.mp_group(group='TestGroupTwo')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_two(val):
            assert not shared_state
            shared_state['test_two_destructive'] = True
            shared_state['all_destructive'] = True


        @pytest.mark.mp_group('TestGroupThree', strategy='free')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_three(val):
            assert not shared_state
            shared_state['test_three_destructive'] = True
            shared_state['all_destructive'] = True

    """)

    result = testdir.runpytest_subprocess('--mp')
    result.assert_outcomes(passed=15)


def test_serial(testdir):
    """Confirms that there is only shared state in groups using serial strategy
    This is an unintuitive testing approach in that it only checks for side effects.
    """
    testdir.makepyfile("""
        import pytest

        shared_state = dict()  # Should only contain group's state changes w/ serial

        @pytest.mark.mp_group('TestGroup', 'serial')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_one(val):
            assert 'test_two_destructive' not in shared_state
            assert 'test_three_destructive' not in shared_state
            if val == 0:
                shared_state['test_one_destructive'] = True
            else:
                assert 'test_one_destructive' in shared_state


        @pytest.mark.mp_group('TestGroupTwo', strategy='serial')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_two(val):
            assert 'test_one_destructive' not in shared_state
            assert 'test_three_destructive' not in shared_state
            if val == 0:
                shared_state['test_two_destructive'] = True
            else:
                assert 'test_two_destructive' in shared_state


        @pytest.mark.mp_group(group='TestGroupThree', strategy='serial')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_three(val):
            assert 'test_one_destructive' not in shared_state
            assert 'test_two_destructive' not in shared_state
            if val == 0:
                shared_state['test_three_destructive'] = True
            else:
                assert 'test_three_destructive' in shared_state


    """)

    result = testdir.runpytest_subprocess('--mp')
    result.assert_outcomes(passed=15)


def test_isolated_free(testdir):
    testdir.makepyfile("""
        import pytest

        shared_state = dict()  # Should always be empty in free strategy

        @pytest.mark.mp_group('TestGroup', 'isolated_free')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_one(val):
            assert not shared_state
            shared_state['test_one_destructive'] = True
            shared_state['all_destructive'] = True


        @pytest.mark.mp_group('TestGroupTwo', strategy='isolated_free')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_two(val):
            assert not shared_state
            shared_state['test_two_destructive'] = True
            shared_state['all_destructive'] = True


        @pytest.mark.mp_group(group='TestGroupThree', strategy='isolated_free')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_three(val):
            assert not shared_state
            shared_state['test_three_destructive'] = True
            shared_state['all_destructive'] = True

    """)

    result = testdir.runpytest_subprocess('--mp')
    result.assert_outcomes(passed=15)


def test_isolated_serial(testdir):
    testdir.makepyfile("""
        import pytest

        shared_state = dict()  # Should only contain group's state changes w/ serial

        @pytest.mark.mp_group('TestGroup', 'isolated_serial')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_one(val):
            assert 'test_two_destructive' not in shared_state
            assert 'test_three_destructive' not in shared_state
            if val == 0:
                shared_state['test_one_destructive'] = True
            else:
                assert 'test_one_destructive' in shared_state


        @pytest.mark.mp_group('TestGroupTwo', strategy='isolated_serial')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_two(val):
            assert 'test_one_destructive' not in shared_state
            assert 'test_three_destructive' not in shared_state
            if val == 0:
                shared_state['test_two_destructive'] = True
            else:
                assert 'test_two_destructive' in shared_state


        @pytest.mark.mp_group(group='TestGroupThree', strategy='isolated_serial')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_three(val):
            assert 'test_one_destructive' not in shared_state
            assert 'test_two_destructive' not in shared_state
            if val == 0:
                shared_state['test_three_destructive'] = True
            else:
                assert 'test_three_destructive' in shared_state

    """)

    result = testdir.runpytest_subprocess('--mp')
    result.assert_outcomes(passed=15)


@pytest.mark.parametrize("c", range(0, 8))
@pytest.mark.parametrize("strategy1", ["isolated_free", "isolated_serial"])
@pytest.mark.parametrize("strategy2", ["free", "serial"])
@pytest.mark.parametrize("clique_size", [1, 2, 4])
def test_isolated_with_other_strategies(c, strategy1, strategy2, clique_size, testdir, tmpdir):
    testdir.makepyfile("""
        import pytest
        import py, time, random

        @pytest.fixture(scope='function')
        def clique_dir(mp_clique_id):
            tempdir = py.path.local('{tmpdir_path}')
            return tempdir.ensure_dir(str(mp_clique_id))

        @pytest.mark.mp_group('TestGroup1', '{strategy1}')
        def test_strategy1(clique_dir):
            assert len(clique_dir.listdir()) == 0, clique_dir.listdir()
            newdir = clique_dir.mkdir('strategy1')
            time.sleep(random.random()*0.1)
            assert len(clique_dir.listdir()) == 1, clique_dir.listdir()
            time.sleep(random.random()*0.1)
            newdir.remove()

        @pytest.mark.mp_group('TestGroup2', '{strategy2}')
        def test_strategy2(clique_dir):
            assert len(clique_dir.listdir()) == 0, clique_dir.listdir()
            newdir = clique_dir.mkdir('strategy2')
            time.sleep(random.random()*0.1)
            assert len(clique_dir.listdir()) == 1, clique_dir.listdir()
            time.sleep(random.random()*0.1)
            newdir.remove()

        @pytest.mark.mp_group('TestGroup3', '{strategy1}')
        def test_strategy3(clique_dir):
            assert len(clique_dir.listdir()) == 0, clique_dir.listdir()
            newdir = clique_dir.mkdir('strategy3')
            time.sleep(random.random()*0.1)
            assert len(clique_dir.listdir()) == 1, clique_dir.listdir()
            time.sleep(random.random()*0.1)
            newdir.remove()

        @pytest.mark.mp_group('TestGroup4', '{strategy1}')
        def test_strategy4(clique_dir):
            assert len(clique_dir.listdir()) == 0, clique_dir.listdir()
            newdir = clique_dir.mkdir('strategy4')
            time.sleep(random.random()*0.1)
            assert len(clique_dir.listdir()) == 1, clique_dir.listdir()
            time.sleep(random.random()*0.1)
            newdir.remove()

    """.format(tmpdir_path=tmpdir.strpath, strategy1=strategy1, strategy2=strategy2))

    result = testdir.runpytest_subprocess('--mp', '--np=2', *['--mp-clique=--np=2' for _ in range(clique_size)])
    result.assert_outcomes(passed=4)
    assert len(tmpdir.listdir()) == clique_size
    assert result.ret == 0
