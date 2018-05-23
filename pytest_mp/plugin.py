from contextlib import contextmanager
import multiprocessing
import collections

from _pytest import main
import psutil
import pytest


def pytest_addoption(parser):
    group = parser.getgroup('pytest-mp')

    mp_help = 'Distribute test groups via multiprocessing.'
    group.addoption('--mp', '--multiprocessing', action='store_true', dest='use_mp', default=None, help=mp_help)

    np_help = 'Set the concurrent worker amount (defaults to cpu count).  Value of 0 disables pytest-mp.'
    group.addoption('--np', '--num-processes', type=int, action='store', dest='num_processes', help=np_help)

    parser.addini('mp', mp_help, type='bool', default=False)
    parser.addini('num_processes', np_help)

    # Includes pytest-instafail functionality
    # :copyright: (c) 2013-2016 by Janne Vanhala.
    # since it isn't compatible w/ MPTerminalReporter

    group.addoption('--instafail', action="store_true", dest="instafail", default=False,
                    help="show failures and errors instantly as they occur (disabled by default).")


manager = multiprocessing.Manager()
# Used for "global" synchronization access.
synchronization = dict(manager=manager)
synchronization['fixture_message_board'] = manager.dict()
synchronization['fixture_lock'] = manager.Lock()

state_fixtures = dict(use_mp=False, num_processes=None)


@pytest.fixture(scope='session')
def mp_use_mp():
    return state_fixtures['use_mp']


@pytest.fixture(scope='session')
def mp_num_processes():
    return state_fixtures['num_processes']


@pytest.fixture(scope='session')
def mp_message_board():
    return synchronization['fixture_message_board']


@pytest.fixture(scope='session')
def mp_lock():
    return synchronization['fixture_lock']


@pytest.fixture(scope='session')
def mp_trail():
    message_board = synchronization['fixture_message_board']

    @contextmanager
    def trail(name, state='start'):
        if state not in ('start', 'finish'):
            raise Exception('mp_trail state must be "start" or "finish": {}'.format(state))

        consumer_key = name + '__consumers__'
        with synchronization['fixture_lock']:
            if state == 'start':
                if consumer_key not in message_board:
                    message_board[consumer_key] = 1
                    yield True
                else:
                    message_board[consumer_key] += 1
                    yield False
            else:
                message_board[consumer_key] -= 1
                if message_board[consumer_key]:
                    yield False
                else:
                    del message_board[consumer_key]
                    yield True

    return trail


def load_mp_options(session):
    """Return use_mp, num_processes from pytest session"""
    if session.config.option.use_mp is None:
        if not session.config.getini('mp'):
            state_fixtures['use_mp'] = False
            state_fixtures['num_processes'] = 0
            return False, 0

    if hasattr(session.config.option, 'num_processes') and session.config.option.num_processes is not None:
        num_processes = session.config.option.num_processes
    else:
        num_processes = session.config.getini('num_processes') or 'cpu_count'

    if num_processes == 'cpu_count':
        num_processes = multiprocessing.cpu_count()
    else:
        try:
            num_processes = int(num_processes)
        except ValueError:
            raise ValueError('--num-processes must be an integer.')

    state_fixtures['use_mp'] = True
    state_fixtures['num_processes'] = num_processes
    return True, num_processes


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


def submit_test_to_process(test, session):
    proc = multiprocessing.Process(target=run_test, args=(test, None, session, synchronization['trigger_process_loop']))
    with synchronization['processes_lock']:
        proc.start()
        pid = proc.pid
        synchronization['running_pids'][pid] = True
        synchronization['processes'][pid] = proc
    synchronization['trigger_process_loop'].set()


def submit_batch_to_process(batch, session):

    def run_batch(tests, finished_signal):
        for i, test in enumerate(tests):
            next_test = tests[i + 1] if i + 1 < len(tests) else None
            test.config.hook.pytest_runtest_protocol(item=test, nextitem=next_test)
            if session.shouldstop:
                raise session.Interrupted(session.shouldstop)
        finished_signal.set()

    proc = multiprocessing.Process(target=run_batch, args=(batch['tests'], synchronization['trigger_process_loop']))
    with synchronization['processes_lock']:
        proc.start()
        pid = proc.pid
        synchronization['running_pids'][pid] = True
        synchronization['processes'][pid] = proc
    synchronization['trigger_process_loop'].set()


def reap_finished_processes():
    with synchronization['processes_lock']:
        pid_list = list(synchronization['finished_pids'].keys())

    for pid in pid_list:
        synchronization['processes'][pid].join()
        del synchronization['processes'][pid]
        del synchronization['finished_pids'][pid]


def run_batched_tests(batches, session, num_processes):

    sorting = dict(free=0, serial=0, isolated_free=1, isolated_serial=2)

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
                synchronization['can_submit_tests'].wait()
                synchronization['can_submit_tests'].clear()
                submit_test_to_process(test, session)
                reap_finished_processes()
        elif strategy == 'serial':
            synchronization['can_submit_tests'].wait()
            synchronization['can_submit_tests'].clear()
            submit_batch_to_process(batches[batch], session)
            reap_finished_processes()
        elif strategy == 'isolated_free':
            synchronization['no_running_tests'].wait()
            synchronization['no_running_tests'].clear()
            for test in batches[batch]['tests']:
                synchronization['can_submit_tests'].wait()
                synchronization['can_submit_tests'].clear()
                submit_test_to_process(test, session)
                reap_finished_processes()
            synchronization['no_running_tests'].wait()
            synchronization['no_running_tests'].clear()
        elif strategy == 'isolated_serial':
            synchronization['no_running_tests'].wait()
            synchronization['no_running_tests'].clear()
            submit_batch_to_process(batches[batch], session)
            reap_finished_processes()
            synchronization['no_running_tests'].wait()
            synchronization['no_running_tests'].clear()
        else:
            raise Exception('Unknown strategy {}'.format(strategy))

    synchronization['no_running_tests'].wait()
    reap_finished_processes()


def process_loop(num_processes):
    while True:
        triggered = synchronization['trigger_process_loop'].wait(.025)
        if triggered:
            synchronization['trigger_process_loop'].clear()

        with synchronization['processes_lock']:
            pid_list = list(synchronization['running_pids'].keys())
        if not pid_list:
            synchronization['no_running_tests'].set()
        elif synchronization['no_running_tests'].is_set():
            synchronization['no_running_tests'].clear()

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
                del synchronization['running_pids'][pid]
                synchronization['finished_pids'][pid] = True
            num_pids -= 1

        if synchronization['reap_process_loop'].is_set() and len(synchronization['running_pids']) == 0:
            return
        if num_pids < num_processes and not synchronization['can_submit_tests'].is_set():
            synchronization['can_submit_tests'].set()


def pytest_runtestloop(session):
    if (session.testsfailed and not session.config.option.continue_on_collection_errors):
        raise session.Interrupted("{} errors during collection".format(session.testsfailed))

    if session.config.option.collectonly:
        return True

    use_mp, num_processes = load_mp_options(session)

    batches = batch_tests(session)

    if not use_mp or not num_processes:
        return main.pytest_runtestloop(session)

    synchronization['stats'] = manager.dict()
    synchronization['stats_lock'] = multiprocessing.Lock()
    synchronization['stats']['failed'] = False

    synchronization['can_submit_tests'] = multiprocessing.Event()
    synchronization['trigger_process_loop'] = multiprocessing.Event()
    synchronization['trigger_process_loop'].set()
    synchronization['no_running_tests'] = multiprocessing.Event()
    synchronization['reap_process_loop'] = multiprocessing.Event()
    synchronization['processes_lock'] = multiprocessing.Lock()
    synchronization['running_pids'] = manager.dict()
    synchronization['finished_pids'] = manager.dict()
    synchronization['processes'] = dict()

    proc_loop = multiprocessing.Process(target=process_loop, args=(num_processes,))
    proc_loop.start()

    run_batched_tests(batches, session, num_processes)

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

    if config.option.use_mp is None:
        if not config.getini('mp'):
            return

    if config.option.xmlpath is not None:
        from pytest_mp.junitxml import MPLogXML
        synchronization['node_reporters'] = manager.list()
        synchronization['node_reporters_lock'] = manager.Lock()
        xmlpath = config.option.xmlpath
        config.pluginmanager.unregister(config._xml)
        config._xml = MPLogXML(xmlpath, config.option.junitprefix, config.getini("junit_suite_name"), manager)
        config.pluginmanager.register(config._xml, 'mpjunitxml')
