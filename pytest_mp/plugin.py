from argparse import Namespace
from contextlib import contextmanager
from copy import copy
from random import choice
import collections
import multiprocessing
import shlex
import sys

from _pytest import main
import psutil
import pytest


def pytest_addoption(parser):
    group = parser.getgroup('pytest-mp')

    mp_help = 'Distribute test groups via multiprocessing.'
    group.addoption('--mp', '--multiprocessing', action='store_true', dest='use_mp', default=None, help=mp_help)

    np_help = 'Set the concurrent worker amount (defaults to cpu count).  Value of 0 disables pytest-mp.'
    group.addoption('--np', '--num-processes', type=int, action='store', dest='num_processes', help=np_help)

    mp_clique_help = 'Create a clique. Each clique has the number of processes set by `--np`. ' \
                   'The parameter of a clique is a string contains one or more pytest command line options. ' \
                   'Resources between cliques are assumed to be isolated, so they can run tests in parallel, ' \
                   'even if the tests are in isolate_* groups. ' \
                   'If no clique is created, there will be a default clique with no pytest option.'
    group.addoption('--mp-clique', action='append', dest='mp_cliques', metavar='PYTEST_OPTIONS', help=mp_clique_help)

    parser.addini('mp', mp_help, type='bool', default=False)
    parser.addini('num_processes', np_help)
    parser.addini('mp_cliques', mp_clique_help, type='args')

    # Includes pytest-instafail functionality
    # :copyright: (c) 2013-2016 by Janne Vanhala.
    # since it isn't compatible w/ MPTerminalReporter

    group.addoption('--instafail', action="store_true", dest="instafail", default=False,
                    help="show failures and errors instantly as they occur (disabled by default).")


def pytest_addhooks(pluginmanager):
    import pytest_mp.hookspec as hookspec
    pluginmanager.add_hookspecs(hookspec)


manager = multiprocessing.Manager()
# Used for "global" synchronization access.
synchronization = dict(manager=manager)
mp_options = Namespace(use_mp=False, num_processes=0, clique_options=[])


@pytest.fixture(scope='session')
def mp_use_mp():
    return getattr(mp_options, 'use_mp', False)


@pytest.fixture(scope='session')
def mp_num_processes():
    return getattr(mp_options, 'num_processes', 0)


@pytest.fixture(scope='session')
def mp_clique_options():
    return getattr(mp_options, 'clique_options', [])


@pytest.fixture(scope='session')
def mp_clique_id():
    return synchronization.get('clique_id', 0)


@pytest.fixture(scope='session')
def mp_message_board(mp_clique_id):
    return synchronization['fixture_message_board'][mp_clique_id]


@pytest.fixture(scope='session')
def mp_lock(mp_clique_id):
    return synchronization['fixture_lock'][mp_clique_id]


@pytest.fixture(scope='session')
def mp_trail(mp_message_board, mp_lock):
    @contextmanager
    def trail(name, state='start'):
        if state not in ('start', 'finish'):
            raise Exception('mp_trail state must be "start" or "finish": {}'.format(state))

        consumer_key = name + '__consumers__'
        with mp_lock:
            if state == 'start':
                if consumer_key not in mp_message_board:
                    mp_message_board[consumer_key] = 1
                    yield True
                else:
                    mp_message_board[consumer_key] += 1
                    yield False
            else:
                mp_message_board[consumer_key] -= 1
                if mp_message_board[consumer_key]:
                    yield False
                else:
                    del mp_message_board[consumer_key]
                    yield True

    return trail


def load_mp_options(config):
    """Return use_mp, num_processes, clique_options from pytest config"""
    if config.option.use_mp is None:
        if not config.getini('mp'):
            return

    if hasattr(config.option, 'num_processes') and config.option.num_processes is not None:
        num_processes = config.option.num_processes
    else:
        num_processes = config.getini('num_processes') or 'cpu_count'

    if num_processes == 'cpu_count':
        num_processes = multiprocessing.cpu_count()
    else:
        try:
            num_processes = int(num_processes)
        except ValueError:
            raise ValueError('--num-processes must be an integer.')

    if getattr(config.option, 'mp_cliques', []):
        mp_cliques_args = config.option.mp_cliques
    else:
        mp_cliques_args = config.getini('mp_cliques') or []

    clique_options = []
    for arg in mp_cliques_args:
        args = shlex.split(arg)
        option = copy(config.option)
        option, unknown = config._parser.parse_known_and_unknown_args(args, namespace=option)
        if unknown:
            raise ValueError('unknown parameter for --mp-clique {}'.format(unknown))
        clique_options.append(option)

    # Call hooks of pytest_mp_configure
    config.pluginmanager.hook.pytest_mp_configure(clique_options=clique_options)

    mp_options.use_mp = True
    mp_options.num_processes = num_processes
    mp_options.clique_options = clique_options


def get_item_batch_name_and_strategy(item):
    marker = item.get_marker('mp_group')
    if marker is None:
        return None, None

    group_name = None
    group_strategy = None

    marker_args = getattr(marker, 'args', None)
    marker_kwargs = getattr(marker, 'kwargs', {})

    # In general, multiple mp_group decorations aren't supported.
    # This is a best effort, since kwargs will be overwritten.
    distilled = list(marker_args) + list(marker_kwargs.values())
    if len(distilled) > 2 \
       or (len(distilled) == 2 and 'strategy' not in marker_kwargs
           and not any([x in distilled for x in ('free', 'isolated_free', 'serial', 'isolated_serial')])):
        raise Exception('Detected too many mp_group values for {}'.format(item.name))

    if marker_args:
        group_name = marker_args[0]
        if len(marker_args) > 1:
            group_strategy = marker_args[1]

    if marker_kwargs:
        group_name = group_name or marker_kwargs.get('group')
        group_strategy = group_strategy or marker_kwargs.get('strategy')

    return group_name, group_strategy


def batch_tests(session):
    batches = collections.OrderedDict()

    for item in session.items:
        group_name, group_strategy = get_item_batch_name_and_strategy(item)

        if group_name is None:
            item.add_marker(pytest.mark.mp_group_info.with_args(group='ungrouped', strategy='free'))
            if 'ungrouped' not in batches:
                batches['ungrouped'] = dict(strategy='free', tests=[])
            batches['ungrouped']['tests'].append(item)
        else:
            if group_strategy is None:
                group_strategy = batches.get(group_name, {}).get('strategy') or 'free'
            elif 'strategy' in batches.get(group_name, []) and batches[group_name]['strategy'] != group_strategy:
                raise Exception("{} already has specified strategy {}."
                                .format(group_name, batches[group_name]['strategy']))
            if group_name not in batches:
                batches[group_name] = dict(strategy=group_strategy, tests=[])
            item.add_marker(pytest.mark.mp_group_info.with_args(group=group_name, strategy=group_strategy))
            batches[group_name]['tests'].append(item)

    total_tests = 0
    for group in batches:
        for test in batches[group]['tests']:
            total_tests += 1

    print('There should be {} tests run.'.format(total_tests))

    return batches


def run_test(test, next_test, session, finished_signal=None):
    test.config.hook.pytest_runtest_protocol(item=test, nextitem=next_test)
    if session.shouldstop:
        raise session.Interrupted(session.shouldstop)
    if finished_signal:
        finished_signal.set()


def run_isolated_serial_batch(batch, final_test, session, finished_signal=None):
    tests = batch['tests']
    for i, test in enumerate(tests):
        next_test = tests[i + 1] if i + 1 < len(tests) else None
        next_test = final_test or next_test
        run_test(test, next_test, session)
    if finished_signal:
        finished_signal.set()
    return


def prefork(session, clique_options, clique_id):
    # Configure the clique before fork
    if clique_options:
        synchronization['clique_id'] = clique_id
        session.config.option = clique_options[clique_id]
        session.config.pluginmanager.hook.pytest_mp_prefork(clique_id=clique_id)


def submit_test_to_process(test, session, clique_options, clique_id):
    prefork(session, clique_options, clique_id)
    proc = multiprocessing.Process(target=run_test, args=(test, None, session, synchronization['trigger_process_loop']))
    with synchronization['processes_lock']:
        proc.start()
        pid = proc.pid
        synchronization['running_pids'][pid] = clique_id
    synchronization['processes'][pid] = proc
    synchronization['clique_status'][clique_id].size += 1
    synchronization['trigger_process_loop'].set()


def submit_batch_to_process(batch, session, clique_options, clique_id):

    def run_batch(tests, finished_signal):
        for i, test in enumerate(tests):
            next_test = tests[i + 1] if i + 1 < len(tests) else None
            test.config.hook.pytest_runtest_protocol(item=test, nextitem=next_test)
            if session.shouldstop:
                raise session.Interrupted(session.shouldstop)
        finished_signal.set()

    prefork(session, clique_options, clique_id)
    proc = multiprocessing.Process(target=run_batch, args=(batch['tests'], synchronization['trigger_process_loop']))
    with synchronization['processes_lock']:
        proc.start()
        pid = proc.pid
        synchronization['running_pids'][pid] = clique_id
    synchronization['processes'][pid] = proc
    synchronization['clique_status'][clique_id].size += 1
    synchronization['trigger_process_loop'].set()


def reap_finished_processes():
    synchronization['process_finished'].wait()
    synchronization['process_finished'].clear()

    with synchronization['processes_lock']:
        finished_pids = dict(synchronization['finished_pids'])
        synchronization['finished_pids'].clear()

    for pid, clique_id in finished_pids.items():
        synchronization['processes'][pid].join()
        del synchronization['processes'][pid]

        synchronization['clique_status'][clique_id].size -= 1
        assert synchronization['clique_status'][clique_id].size >= 0
        if synchronization['clique_status'][clique_id].size == 0:
            synchronization['clique_status'][clique_id].barrier = False


def wait_until_no_running():
    """ Wait until all processes are reaped """
    while sum([gs.size for gs in synchronization['clique_status']]):
        reap_finished_processes()


def wait_until_new_barrier():
    """
    Wait until at least one new barrier is set.
    Return a set of cliques having set barrier.
    """
    new_barrier_cliques = set()
    while True:
        for i in range(len(synchronization['clique_status'])):
            if synchronization['clique_status'][i].size == 0:
                synchronization['clique_status'][i].barrier = True
                new_barrier_cliques.add(i)

        if new_barrier_cliques:
            return new_barrier_cliques

        reap_finished_processes()


def wait_until_can_submit(num_processes):
    """
    Wait until at leat a clique in is available.
    Return a list of cliques with minimal size.
    """
    while True:
        min_cliques, min_size = [], sys.maxint
        for i in range(len(synchronization['clique_status'])):
            if synchronization['clique_status'][i].size >= num_processes:
                continue

            if synchronization['clique_status'][i].size == 0:
                synchronization['clique_status'][i].barrier = False

            if not synchronization['clique_status'][i].barrier:
                if synchronization['clique_status'][i].size < min_size:
                    min_size = synchronization['clique_status'][i].size
                    min_cliques = [i]
                elif synchronization['clique_status'][i].size == min_size:
                    min_cliques.append(i)

            if min_cliques:
                return min_cliques

        reap_finished_processes()


def wait_until_can_submit_with_barrier(num_processes, barrier_cliques):
    """
    Wait until at least a clique in `barrier_cliques` is available.
    Return a list of cliques with minimal size.

    If a clique has size 0, add it into `barrier_cliques`.
    """
    while True:
        min_cliques, min_size = [], sys.maxint
        for i in range(len(synchronization['clique_status'])):
            if synchronization['clique_status'][i].size >= num_processes:
                continue

            if synchronization['clique_status'][i].size == 0:
                synchronization['clique_status'][i].barrier = True
                barrier_cliques.add(i)

            if i in barrier_cliques:
                assert synchronization['clique_status'][i].barrier
                if synchronization['clique_status'][i].size < min_size:
                    min_size = synchronization['clique_status'][i].size
                    min_cliques = [i]
                elif synchronization['clique_status'][i].size == min_size:
                    min_cliques.append(i)

            if min_cliques:
                return min_cliques

        reap_finished_processes()


def run_batched_tests(batches, session, num_processes, clique_options):
    sorting = dict(free=2, serial=2, isolated_free=1, isolated_serial=0)

    batch_names = sorted(batches.keys(), key=lambda x: sorting.get(batches[x]['strategy'], 3))

    if not num_processes:
        for i, batch in enumerate(batch_names):
            next_test = batches[batch_names[i + 1]]['tests'][0] if i + 1 < len(batch_names) else None
            run_isolated_serial_batch(batches[batch], next_test, session)
        return

    for batch in batch_names:
        strategy = batches[batch]['strategy']
        if strategy == 'free':
            for test in batches[batch]['tests']:
                cliques = wait_until_can_submit(num_processes)
                submit_test_to_process(test, session, clique_options, choice(cliques))
        elif strategy == 'serial':
            cliques = wait_until_can_submit(num_processes)
            submit_batch_to_process(batches[batch], session, clique_options, choice(cliques))
        elif strategy == 'isolated_free':
            barrier_cliques = wait_until_new_barrier()
            for test in batches[batch]['tests']:
                cliques = wait_until_can_submit_with_barrier(num_processes, barrier_cliques)
                submit_test_to_process(test, session, clique_options, choice(cliques))
        elif strategy == 'isolated_serial':
            barrier_cliques = wait_until_new_barrier()
            submit_batch_to_process(batches[batch], session, clique_options, choice(list(barrier_cliques)))
        else:
            raise Exception('Unknown strategy {}'.format(strategy))

    wait_until_no_running()


def process_loop(num_processes):
    while True:
        triggered = synchronization['trigger_process_loop'].wait(.1)
        if triggered:
            synchronization['trigger_process_loop'].clear()

        with synchronization['processes_lock']:
            pid_list = list(synchronization['running_pids'].keys())

        num_pids = len(pid_list)

        for pid in pid_list:
            try:
                proc = psutil.Process(pid)
                if proc.status() not in ('stopped', 'zombie'):
                    continue
            except psutil.NoSuchProcess:
                pass
            except IOError:
                continue
            with synchronization['processes_lock']:
                synchronization['finished_pids'][pid] = synchronization['running_pids'].pop(pid)

            synchronization['process_finished'].set()
            num_pids -= 1

        if synchronization['reap_process_loop'].is_set() and len(synchronization['running_pids']) == 0:
            return


def pytest_runtestloop(session):
    if (session.testsfailed and not session.config.option.continue_on_collection_errors):
        raise session.Interrupted("{} errors during collection".format(session.testsfailed))

    if session.config.option.collectonly:
        return True

    use_mp, num_processes, clique_options = mp_options.use_mp, mp_options.num_processes, mp_options.clique_options
    if clique_options:
        synchronization['fixture_message_board'] = [manager.dict() for _ in clique_options]
        synchronization['fixture_lock'] = [manager.Lock() for _ in clique_options]
    else:
        synchronization['fixture_message_board'] = [manager.dict()]
        synchronization['fixture_lock'] = [manager.Lock()]

    batches = batch_tests(session)

    if not use_mp or not num_processes:
        return main.pytest_runtestloop(session)

    synchronization['stats'] = manager.dict()
    synchronization['stats_lock'] = multiprocessing.Lock()
    synchronization['stats']['failed'] = False

    synchronization['trigger_process_loop'] = multiprocessing.Event()
    synchronization['trigger_process_loop'].set()
    synchronization['process_finished'] = multiprocessing.Event()
    synchronization['reap_process_loop'] = multiprocessing.Event()
    synchronization['processes_lock'] = multiprocessing.Lock()
    synchronization['running_pids'] = manager.dict() # pid -> clique_id
    synchronization['finished_pids'] = manager.dict() # pid -> clique_id
    synchronization['processes'] = dict() # pid -> multiprocessing.Process

    # Use barrier to isolate groups. It can only be set/unset when clique size is 0
    synchronization['clique_status'] = [Namespace(size=0, barrier=False) for _ in clique_options]
    if not synchronization['clique_status']:
        # Create an implicit clique
        synchronization['clique_status'] = [Namespace(size=0, barrier=False)]

    proc_loop = multiprocessing.Process(target=process_loop, args=(num_processes,))
    proc_loop.start()

    run_batched_tests(batches, session, num_processes, clique_options)

    synchronization['reap_process_loop'].set()
    proc_loop.join()

    if synchronization['stats']['failed']:
        session.testsfailed = True

    return True


def pytest_runtest_logreport(report):
    # Keep flag of failed tests for session.testsfailed, which decides return code.
    if 'stats' in synchronization:
        with synchronization['stats_lock']:
            if report.failed and not synchronization['stats']['failed']:
                if report.when == 'call':
                    synchronization['stats']['failed'] = True


@pytest.mark.trylast
def pytest_configure(config):
    config.addinivalue_line('markers',
                            "mp_group('GroupName', strategy): test (suite) is in named "
                            "grouped w/ desired strategy: 'free' (default), 'serial', "
                            "'isolated_free', or 'isolated_serial'.")

    standard_reporter = config.pluginmanager.get_plugin('terminalreporter')
    if standard_reporter:
        from pytest_mp.terminal import MPTerminalReporter
        mp_reporter = MPTerminalReporter(standard_reporter, manager)
        config.pluginmanager.unregister(standard_reporter)
        config.pluginmanager.register(mp_reporter, 'terminalreporter')

    load_mp_options(config)
    if not mp_options.use_mp:
        return

    if config.option.xmlpath is not None:
        from pytest_mp.junitxml import MPLogXML
        synchronization['node_reporters'] = manager.list()
        synchronization['node_reporters_lock'] = manager.Lock()
        xmlpath = config.option.xmlpath
        config.pluginmanager.unregister(config._xml)
        config._xml = MPLogXML(xmlpath, config.option.junitprefix, config.getini("junit_suite_name"), manager)
        config.pluginmanager.register(config._xml, 'mpjunitxml')
