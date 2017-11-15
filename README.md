# pytest-mp: Multiprocess and Segregate Tests

[![Build Status](https://travis-ci.org/ansible/pytest-mp.svg?branch=master)](https://travis-ci.org/ansible/pytest-mp)

**pytest-mp** is a minimalist approach to distributing and segregating pytest tests across processes using python's [multiprocessing](https://docs.python.org/2/library/multiprocessing.html) library and is heavily inspired by [pytest-concurrent](https://github.com/reverbc/pytest-concurrent) and [pytest-xdist](https://github.com/pytest-dev/pytest-xdist).  As a very early beta, it doesn't pledge or intend to support the majority of platforms or use cases.  Design is based on supporting slow, io-bound testing with often tedious system under test configuration that can benefit from running several tests at one time.

### Installation and Basic Usage
```bash
git clone https://github.com/ansible/pytest-mp
pip install pytest-mp/
cd my_test_dir
# Most basic invocation that will spin up to as many test runner processes as multiprocessing.cpu_count() indicates.
pytest --mp
# Create up to 4 concurrent child processes.
pytest --mp --np 4
pytest --multiprocessing --num-processes 4  # Same as above but with more informative option names.
```


### Test Running and Segregation Strategies
pytest-mp provides four test segregation strategies that come in handy for common test and fixture patterns.  Each strategy has its own performance (dis)advantages and caveats in terms of fixture scoping and invocations.

```python
import pytest

@pytest.mark.mp_group('SomeGroupName', 'free')  # free, serial, isolated_free, or isolated_serial
class TestSomething(object):

    def test_one(self, fixture_one):
        assert True

    def test_two(self, fixture_two):
        assert True


@pytest.mark.mp_group('SomeAdditionalGroupName')  # uses free strategy by default
def test_three():
    assert True


@pytest.mark.mp_group(group='SomeOtherGroupName', strategy='isolated_serial')
def test_four(fixture_three):
    assert True


@pytest.mark.mp_group('SomeOtherGroupName')  # still uses previously-defined strategy isolated_serial
def test_five(fixture_three):
    assert True
```

1. The **`free`** strategy distributes each test in a group to a fresh pytest session in a child process that invokes all sourced fixtures (regardless of scope), runs that single test, and calls all registered finalizers before joining.  This is the default test strategy for grouped and ungrouped tests.
1. The **`serial`** strategy distributes each group of tests to a fresh pytest session in a child process that invokes all sourced fixtures (regardless of scope) and runs each test serially in the same process before tearing down.  This group is best suited for tests that require shared, highly-scoped fixtures that won't affect the state of the system under test for other tests.
1. The **`isolated_free`** strategy is the same as `free`, but all tests in this group will be run separately in time from any other test group.  Best suited for tests with noisy or destructive fixtures that would affect the requirements of other tests, but that don't require a shared process.
1. The **`isolated_serial`** strategy is the same as `serial`, but all tests in this group will be run separate in time from any other test group, essentially like a regular pytest invocation.  Best suited for tests with shared, noisy, or destructive fixtures.  Absolute pytest execution will be limited to a single process while these tests are running.

For example, of the tests defined above, `TestSomething.test_one`, `TestSomething.test_two`, and `test_three` could potentially be run at the same time among 3 processes, but `test_four` and `test_five` are guaranteed to run in the same process and with no other tests running in the background.

### Synchronization
Given that tests generally run in child processes that emulate a fresh pytest session and that by nature pytest fixtures of class or greater scope are designed to be shared and invoked once by the test runner, some synchronization between test processes is needed to provide idempotency.  pytest-mp provides two session-scoped synchronization fixtures: `mp_message_board` and `mp_lock`, a `multiprocesssing.Manager.dict()` and `multiprocessing.Manager.Lock()` instance, respectively.

```python
import pytest

@pytest.fixture(scope='session')
def must_be_idempotent_without_teardown(mp_lock, mp_message_board, some_resource):
    with mp_lock:
        if mp_message_board.get('some_flag_your_fixture_creates'):
            return
        mp_message_board['some_flag_your_fixture_creates'] = True
        some_resource.destructive_call()
    return

@pytest.fixture(scope='session')
def must_be_idempotent_with_teardown(mp_lock, mp_message_board, some_resource):
    with mp_lock:
        if mp_message_board.get('must_be_idempotent_setup'):
            yielded = mp_message_board['must_be_idempotent_val']
        else:
            mp_message_board['must_be_idempotent_setup'] = True
            yielded = some_resource.destructive_call()
            mp_message_board['must_be_idempotent_val'] = yielded  # pickle!!!
    yield yielded
    with mp_lock:
        if mp_message_board.get('must_be_idempotent_teardown'):
            return
        mp_message_board['must_be_idempotent_teardown'] = True
        # Notice there is no synchronization w/ this teardown and active fixture consumers!
        some_resource.cleanup()
```

A helper fixture `mp_trail()` that internally uses `mp_lock` and `mp_message_board` is provided to assist in the assurance that a single setup and teardown invocation of shared fixtures and test logic occurs with multiple test runners.  A __trail__ is any named, shared path with single 'start' and 'finish' events made available as context manager values.

```python
@pytest.fixture(scope='session')
def must_be_idempotent_with_teardown(mp_trail, some_resource):
    with mp_trail('TrailName', 'start') as start:  #  mp_trail('TrailName') defaults to 'start'
        if start:  # First invocation of `must_be_idempotent_with_teardown` detected.
            yielded = some_resource.destructive_call()
        else:  # setup has already occured by another test runner
            yielded = some_resource.get_current_state()
    yield yielded
    with mp_trail('TrailName', 'finish') as finish:
        if finish:  # Last finalizer/teardown detected.
            # There are no other tests using this fixture at the moment
            some_resource.cleanup()
```
