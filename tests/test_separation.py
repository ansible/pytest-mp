
def test_isolated_trail_separation(testdir):
    testdir.makepyfile("""
        from contextlib import contextmanager
        from multiprocessing import Manager
        import time

        import pytest


        shared = Manager().dict()


        @contextmanager
        def _trail_fixture(num, mp_trail, request):
            group = request.node.get_closest_marker('mp_group').kwargs['group']
            group += num
            with mp_trail(num) as start:
                if start:
                    shared[num + 'group'] = group
            if 'Shared' in group:
                assert 'Shared' in shared[num + 'group']
            else:
                assert shared[num + 'group'] == group

            yield

            with mp_trail(num, 'finish') as finish:
                pass


        @pytest.fixture
        def trail_fixture_1(mp_trail, request):
            with _trail_fixture('1', mp_trail, request):
                yield


        @pytest.fixture
        def trail_fixture_2(mp_trail, request):
            with _trail_fixture('2', mp_trail, request):
                yield


        @pytest.fixture
        def trail_fixture_3(mp_trail, request):
            with _trail_fixture('3', mp_trail, request):
                yield


        @pytest.fixture
        def trail_fixture_4(mp_trail, request):
            with _trail_fixture('4', mp_trail, request):
                yield


        @pytest.fixture
        def trail_fixture_5(mp_trail, request):
            with _trail_fixture('5', mp_trail, request):
                yield


        @pytest.fixture
        def trail_fixture_6(mp_trail, request):
            with _trail_fixture('6', mp_trail, request):
                yield


        @pytest.fixture
        def trail_fixture_7(mp_trail, request):
            with _trail_fixture('7', mp_trail, request):
                yield


        @pytest.fixture
        def trail_fixture_8(mp_trail, request):
            with _trail_fixture('8', mp_trail, request):
                yield


        @pytest.fixture
        def trail_fixture_9(mp_trail, request):
            with _trail_fixture('9', mp_trail, request):
                yield


        @pytest.fixture
        def trail_fixture_10(mp_trail, request):
            with _trail_fixture('10', mp_trail, request):
                yield


        @pytest.mark.mp_group(group='IsoFree1', strategy='isolated_free')
        @pytest.mark.parametrize('_', range(100))
        def test_iso_free_1(trail_fixture_1, trail_fixture_2, trail_fixture_3,
                            trail_fixture_4, trail_fixture_5, trail_fixture_6,
                            trail_fixture_7, trail_fixture_8, trail_fixture_9,
                            trail_fixture_10, _):
            assert True


        @pytest.mark.mp_group(group='IsoFree2', strategy='isolated_free')
        @pytest.mark.parametrize('_', range(100))
        def test_iso_free_2(trail_fixture_1, trail_fixture_2, trail_fixture_3,
                            trail_fixture_4, trail_fixture_5, trail_fixture_6,
                            trail_fixture_7, trail_fixture_8, trail_fixture_9,
                            trail_fixture_10, _):
            assert True


        @pytest.mark.mp_group(group='IsoFree3', strategy='isolated_free')
        @pytest.mark.parametrize('_', range(100))
        def test_iso_free_3(trail_fixture_1, trail_fixture_2, trail_fixture_3,
                            trail_fixture_4, trail_fixture_5, trail_fixture_6,
                            trail_fixture_7, trail_fixture_8, trail_fixture_9,
                            trail_fixture_10, _):
            assert True


        @pytest.mark.mp_group(group='IsoFree4', strategy='isolated_free')
        @pytest.mark.parametrize('_', range(100))
        def test_iso_free_4(trail_fixture_1, trail_fixture_2, trail_fixture_3,
                            trail_fixture_4, trail_fixture_5, trail_fixture_6,
                            trail_fixture_7, trail_fixture_8, trail_fixture_9,
                            trail_fixture_10, _):
            assert True


        @pytest.mark.mp_group(group='IsoSerial1', strategy='isolated_serial')
        @pytest.mark.parametrize('_', range(50))
        def test_iso_serial_1(trail_fixture_1, trail_fixture_2, trail_fixture_3,
                              trail_fixture_4, trail_fixture_5, trail_fixture_6,
                              trail_fixture_7, trail_fixture_8, trail_fixture_9,
                              trail_fixture_10, _):
            assert True


        @pytest.mark.mp_group(group='IsoSerial2', strategy='isolated_serial')
        @pytest.mark.parametrize('_', range(50))
        def test_iso_serial_2(trail_fixture_1, trail_fixture_2, trail_fixture_3,
                              trail_fixture_4, trail_fixture_5, trail_fixture_6,
                              trail_fixture_7, trail_fixture_8, trail_fixture_9,
                              trail_fixture_10, _):
            assert True


        @pytest.mark.mp_group(group='IsoSerial3', strategy='isolated_serial')
        @pytest.mark.parametrize('_', range(50))
        def test_iso_serial_3(trail_fixture_1, trail_fixture_2, trail_fixture_3,
                              trail_fixture_4, trail_fixture_5, trail_fixture_6,
                              trail_fixture_7, trail_fixture_8, trail_fixture_9,
                              trail_fixture_10, _):
            assert True


        @pytest.mark.mp_group(group='IsoSerial4', strategy='isolated_serial')
        @pytest.mark.parametrize('_', range(50))
        def test_iso_serial_4(trail_fixture_1, trail_fixture_2, trail_fixture_3,
                              trail_fixture_4, trail_fixture_5, trail_fixture_6,
                              trail_fixture_7, trail_fixture_8, trail_fixture_9,
                              trail_fixture_10, _):
            assert True


        @pytest.mark.mp_group(group='Shared1', strategy='free')
        @pytest.mark.parametrize('_', range(200))
        def test_free(trail_fixture_1, trail_fixture_2, trail_fixture_3, trail_fixture_4,
                      trail_fixture_5, trail_fixture_6, trail_fixture_7, trail_fixture_8,
                      trail_fixture_9, trail_fixture_10, _):
            assert True


        @pytest.mark.mp_group(group='Shared2', strategy='serial')
        @pytest.mark.parametrize('_', range(200))
        def test_serial(trail_fixture_1, trail_fixture_2, trail_fixture_3, trail_fixture_4,
                        trail_fixture_5, trail_fixture_6, trail_fixture_7, trail_fixture_8,
                        trail_fixture_9, trail_fixture_10, _):
            assert True
    """)

    result = testdir.runpytest('--mp')
    result.assert_outcomes(passed=1000)
    assert result.ret == 0
