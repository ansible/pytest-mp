from datetime import datetime

import pytest


@pytest.mark.parametrize('use_mp', (True, False))
def test_mp_use_mp(testdir, use_mp):
    testdir.makepyfile("""

    def test_one(mp_use_mp):
        assert mp_use_mp == {}

    """.format(use_mp))

    result = testdir.runpytest_subprocess('--mp' if use_mp else '')
    result.assert_outcomes(passed=1)
    assert result.ret == 0


@pytest.mark.parametrize('num_processes', (1, 100))
def test_mp_num_processes(testdir, num_processes):
    testdir.makepyfile("""

    def test_one(mp_num_processes):
        assert mp_num_processes == {}

    """.format(num_processes))

    result = testdir.runpytest_subprocess('--mp', '--np={}'.format(num_processes))
    result.assert_outcomes(passed=1)
    assert result.ret == 0


@pytest.mark.parametrize('clique_num', (0, 1, 100))
def test_mp_clique_options(testdir, clique_num):
    testdir.makepyfile("""

    def test_one(mp_clique_options):
        assert len(mp_clique_options) == {}
        for option in mp_clique_options:
            assert option.num_processes == 1000

    """.format(clique_num))

    result = testdir.runpytest_subprocess('--mp', *['--mp-clique="--np=1000"' for _ in range(clique_num)])
    result.assert_outcomes(passed=1)
    assert result.ret == 0


def test_mp_clique_id(testdir):
    testdir.makepyfile("""
    import time
    import multiprocessing

    import pytest

    manager = multiprocessing.Manager()
    clique_ids = manager.dict()
    lock = manager.Lock()

    @pytest.mark.mp_group('test_one', 'isolated_serial')
    def test_one(mp_clique_id):
        global clique_ids
        with lock:
            clique_ids[1] = mp_clique_id
        time.sleep(1)

    @pytest.mark.mp_group('test_two', 'isolated_serial')
    def test_two(mp_clique_id):
        global clique_ids
        with lock:
            clique_ids[2] = mp_clique_id
        time.sleep(1)

    def test_three():
        assert clique_ids[1] != clique_ids[2]
        assert 0 in clique_ids.values()
        assert 1 in clique_ids.values()

    """)

    result = testdir.runpytest_subprocess('--mp', '--mp-clique="--np=2"', '--mp-clique="--np=2"')
    result.assert_outcomes(passed=3)
    assert result.ret == 0


def test_mp_lock_blocks_test_exec(request, testdir):
    testdir.makepyfile("""
        from time import sleep

        def test_one(mp_lock):
            with mp_lock:
                sleep(1)
            assert True

        def test_two(mp_lock):
            with mp_lock:
                sleep(1)
            assert True

        def test_three(mp_lock):
            with mp_lock:
                sleep(1)
            assert True

    """)

    t0 = datetime.now()
    result = testdir.runpytest_subprocess('--mp')
    delta = datetime.now() - t0

    result.assert_outcomes(passed=3)
    assert result.ret == 0
    assert delta.total_seconds() >= 3


def test_mp_message_board_available_to_all_tests(testdir):
    testdir.makepyfile("""
        from time import sleep

        def test_one(mp_message_board):
            mp_message_board['hello'] = True


        def test_two(mp_message_board):
            for _ in range(40):
                if 'hello' in mp_message_board:
                    return True
                sleep(.25)
            assert False

    """)

    result = testdir.runpytest_subprocess('--mp')
    result.assert_outcomes(passed=2)
    assert result.ret == 0


def test_mp_trail_happy_path_single_consumer(testdir):
    testdir.makepyfile("""

        def test_mp_trail(mp_trail, mp_message_board):
            with mp_trail('happy_path'*100) as start:
                if start:
                    mp_message_board['happy_path_test_val'] = 123

            assert mp_message_board['happy_path_test_val'] == 123

            with mp_trail('happy_path'*100, 'finish') as finish:
                if finish:
                    mp_message_board['happy_path_test_val'] = 0

            assert mp_message_board['happy_path_test_val'] == 0

    """)

    result = testdir.runpytest_subprocess('--mp')
    result.assert_outcomes(passed=1)
    assert result.ret == 0


def test_mp_trail_single_start(testdir):
    testdir.makepyfile("""
        from time import sleep

        import pytest

        @pytest.mark.parametrize('val', range(100))
        def test_mp_trail(val, mp_trail, mp_message_board):
            with mp_trail('single_start'*100) as start:
                if start:
                    if 'one_start' not in mp_message_board:
                        mp_message_board['one_start'] = 0
                    mp_message_board['one_start'] += 1

            try:
                assert mp_message_board['one_start'] == 1
            except:
                raise Exception(str(id(mp_message_board)))


    """)

    result = testdir.runpytest_subprocess('--mp')
    result.assert_outcomes(passed=100)
    assert result.ret == 0


def test_mp_trail_finish_never_true_with_consumers(testdir):
    testdir.makepyfile("""
        from time import sleep

        import pytest

        @pytest.mark.parametrize('val', range(100))
        def test_mp_trail(val, mp_trail, mp_message_board):
            with mp_trail('finish_without_consumers'*100) as start:
                if 'consumers' not in mp_message_board:
                    mp_message_board['consumers'] = 0
                mp_message_board['consumers'] += 1

            assert mp_message_board['consumers']

            with mp_trail('finish_without_consumers'*100, 'finish') as finish:
                mp_message_board['consumers'] -= 1
                if finish:
                    assert mp_message_board['consumers'] == 0
                else:
                    assert mp_message_board['consumers']

    """)

    result = testdir.runpytest_subprocess('--mp')
    result.assert_outcomes(passed=100)
    assert result.ret == 0
