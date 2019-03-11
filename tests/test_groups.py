import pytest


@pytest.mark.parametrize('use_mp', (False, True))
def test_group_info_marker_kwargs_from_args(testdir, use_mp):
    testdir.makepyfile("""
        import pytest

        @pytest.mark.mp_group('One')
        def test_one(request):
            kwargs = request.node.get_closest_marker('mp_group_info').kwargs
            assert kwargs['group'] == 'One'
            assert kwargs['strategy'] == 'free'

        @pytest.mark.mp_group('One')
        def test_two(request):
            kwargs = request.node.get_closest_marker('mp_group_info').kwargs
            assert kwargs['group'] == 'One'
            assert kwargs['strategy'] == 'free'

        @pytest.mark.mp_group('Two', 'serial')
        def test_three(request):
            kwargs = request.node.get_closest_marker('mp_group_info').kwargs
            assert kwargs['group'] == 'Two'
            assert kwargs['strategy'] == 'serial'

        def test_four(request):
            kwargs = request.node.get_closest_marker('mp_group_info').kwargs
            assert kwargs['group'] == 'ungrouped'
            assert kwargs['strategy'] == 'free'

    """)

    result = testdir.runpytest('--mp' if use_mp else '')
    result.assert_outcomes(passed=4)
    assert result.ret == 0


@pytest.mark.parametrize('use_mp', (False, True))
def test_group_info_marker_kwargs_from_kwargs(testdir, use_mp):
    testdir.makepyfile("""
        import pytest

        @pytest.mark.mp_group(group='One')
        def test_one(request):
            kwargs = request.node.get_closest_marker('mp_group_info').kwargs
            assert kwargs['group'] == 'One'
            assert kwargs['strategy'] == 'free'

        @pytest.mark.mp_group(group='One')
        def test_two(request):
            kwargs = request.node.get_closest_marker('mp_group_info').kwargs
            assert kwargs['group'] == 'One'
            assert kwargs['strategy'] == 'free'

        @pytest.mark.mp_group(group='Two', strategy='serial')
        def test_three(request):
            kwargs = request.node.get_closest_marker('mp_group_info').kwargs
            assert kwargs['group'] == 'Two'
            assert kwargs['strategy'] == 'serial'

        def test_four(request):
            kwargs = request.node.get_closest_marker('mp_group_info').kwargs
            assert kwargs['group'] == 'ungrouped'
            assert kwargs['strategy'] == 'free'

    """)

    result = testdir.runpytest('--mp' if use_mp else '')
    result.assert_outcomes(passed=4)
    assert result.ret == 0


@pytest.mark.parametrize('use_mp', (False, True))
def test_group_info_marker_kwargs_from_args_and_kwargs(testdir, use_mp):
    testdir.makepyfile("""
        import pytest

        @pytest.mark.mp_group('One', strategy='serial')
        def test_one(request):
            kwargs = request.node.get_closest_marker('mp_group_info').kwargs
            assert kwargs['group'] == 'One'
            assert kwargs['strategy'] == 'serial'

        @pytest.mark.mp_group(group='One')
        def test_two(request):
            kwargs = request.node.get_closest_marker('mp_group_info').kwargs
            assert kwargs['group'] == 'One'
            assert kwargs['strategy'] == 'serial'  # inherited

        def test_three(request):
            kwargs = request.node.get_closest_marker('mp_group_info').kwargs
            assert kwargs['group'] == 'ungrouped'
            assert kwargs['strategy'] == 'free'

    """)

    result = testdir.runpytest('--mp' if use_mp else '')
    result.assert_outcomes(passed=3)
    assert result.ret == 0


def test_multiple_groups_disallowed_args(testdir):
    testdir.makepyfile("""
        import pytest

        @pytest.mark.mp_group('One')
        class TestClass(object):

            @pytest.mark.mp_group('Two')
            def test_one(self):
                assert True

    """)

    result = testdir.runpytest('--mp')
    result.stdout.fnmatch_lines(['*Exception: Detected too many mp_group values for test_one',
                                 '*= no tests ran in * seconds =*'])
    assert result.ret == 3


def test_multiple_groups_disallowed_args_and_kwargs(testdir):
    #  It isn't possible to account for just kwargs since they will be set to highest
    #  decorated value (overwritten)
    testdir.makepyfile("""
        import pytest

        @pytest.mark.mp_group('One')
        class TestClass(object):

            @pytest.mark.mp_group(group='Two')
            def test_one(self, request):
                assert True

    """)

    result = testdir.runpytest('--mp')
    result.stdout.fnmatch_lines(['*Exception: Detected too many mp_group values for test_one',
                                 '*= no tests ran in * seconds =*'])
    assert result.ret == 3


def test_confirm_ordering_by_group_strategy(testdir):
    # TODO
    testdir.makepyfile("""
        import pytest

        @pytest.mark.mp_group('IsoSerial', 'isolated_serial')
        def test_a_isolated_serial():
            assert True

        @pytest.mark.mp_group('IsoFree', 'isolated_free')
        @pytest.mark.parametrize('val', range(10))
        def test_b_isolated_free(val):
            assert True

        @pytest.mark.mp_group('Serial', 'serial')
        @pytest.mark.parametrize('val', range(5))
        def test_c_serial(val):
            assert True

        @pytest.mark.mp_group('Free', 'free')
        @pytest.mark.parametrize('val', range(10))
        def test_d_free(val):
            assert True

    """)
    result = testdir.runpytest('-vs', '--mp')
    result.assert_outcomes(passed=26)
    assert result.ret == 0
