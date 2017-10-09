import pytest


strategies = ['free', 'serial', 'isolated_free', 'isolated_serial']


@pytest.mark.parametrize('strategy', strategies)
def test_all_pass(testdir, strategy):
    testdir.makepyfile("""
        import pytest

        @pytest.mark.mp_group('TestGroup', '{0}')
        @pytest.mark.parametrize('val', range(1, 6))
        def test_one(val):
            assert val


        @pytest.mark.mp_group(group='TestGroupTwo', strategy='{0}')
        @pytest.mark.parametrize('val', range(1, 6))
        def test_two(val):
            assert True


        @pytest.mark.mp_group('TestGroupTwo', strategy='{0}')
        @pytest.mark.parametrize('val', range(1, 6))
        def test_three(val):
            assert val

    """.format(strategy))

    result = testdir.runpytest('--mp')
    result.assert_outcomes(passed=15)
    assert result.ret == 0


@pytest.mark.parametrize('strategy', strategies)
def test_pass_and_fail(testdir, strategy):
    testdir.makepyfile("""
        import pytest

        @pytest.mark.mp_group('TestGroup', '{0}')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_one(val):
            assert val


        @pytest.mark.mp_group(group='TestGroupTwo', strategy='{0}')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_two(val):
            assert val


        @pytest.mark.mp_group('TestGroupTwo', strategy='{0}')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_three(val):
            assert val

    """.format(strategy))

    result = testdir.runpytest('--mp')
    result.assert_outcomes(passed=12, failed=3)
    assert result.ret == 1


@pytest.mark.parametrize('strategy', strategies)
def test_pass_fail_and_skip(testdir, strategy):
    testdir.makepyfile("""
        import pytest

        def helper(val):
            if val == 1:
                pytest.skip()
            assert val

        @pytest.mark.mp_group('TestGroup', '{0}')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_one(val):
            helper(val)


        @pytest.mark.mp_group(group='TestGroupTwo', strategy='{0}')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_two(val):
            helper(val)


        @pytest.mark.mp_group('TestGroupTwo', strategy='{0}')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_three(val):
            helper(val)

    """.format(strategy))

    result = testdir.runpytest('--mp')
    result.assert_outcomes(passed=9, failed=3, skipped=3)
    assert result.ret == 1


@pytest.mark.parametrize('strategy', strategies)
def test_pass_fail_skip_and_error(testdir, strategy):
    testdir.makepyfile("""
        import pytest

        @pytest.fixture
        def bomb(request):
            if '2' in request.node.name:
                raise Exception('error')


        def helper(val):
            if val == 1:
                pytest.skip()
            assert val


        @pytest.mark.mp_group('TestGroup', '{0}')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_one(bomb, val):
            helper(val)


        @pytest.mark.mp_group(group='TestGroupTwo', strategy='{0}')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_two(bomb, val):
            helper(val)


        @pytest.mark.mp_group('TestGroupTwo', strategy='{0}')
        @pytest.mark.parametrize('val', range(0, 5))
        def test_three(bomb, val):
            helper(val)

    """.format(strategy))

    result = testdir.runpytest('--mp')
    result.assert_outcomes(passed=6, failed=3, skipped=3, error=3)
    assert result.ret == 1
