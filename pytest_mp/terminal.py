from _pytest.terminal import TerminalReporter

from pytest_mp.plugin import manager


# # Taken from pytest/_pytest/terminal.py
# and made process safe by avoiding use of `setdefault()`
# Thanks to pytest-concurrent for approach


class MPTerminalReporter(TerminalReporter):

    def __init__(self, reporter):
        TerminalReporter.__init__(self, reporter.config)
        self._tw = self.writer = reporter.writer  # some monkeypatching needed to access existing writer
        self.stats = manager.dict()
        self.stats_lock = manager.Lock()

    def pytest_runtest_logreport(self, report):
        rep = report
        res = self.config.hook.pytest_report_teststatus(report=rep)
        cat, letter, word = res

        # This is the only difference from the pytest core TerminalReporter.
        with self.stats_lock:
            cat_list = self.stats.get(cat, [])
            cat_list.append(rep)
            self.stats[cat] = cat_list

        self._tests_ran = True
        if not letter and not word:
            # probably passed setup/teardown
            return
        if self.verbosity <= 0:
            if not hasattr(rep, 'node') and self.showfspath:
                self.write_fspath_result(rep.nodeid, letter)
            else:
                self._tw.write(letter)
        else:
            if isinstance(word, tuple):
                word, markup = word
            else:
                if rep.passed:
                    markup = {'green': True}
                elif rep.failed:
                    markup = {'red': True}
                elif rep.skipped:
                    markup = {'yellow': True}
            line = self._locationline(rep.nodeid, *rep.location)
            if not hasattr(rep, 'node'):
                self.write_ensure_prefix(line, word, **markup)
            else:
                self.ensure_newline()
                if hasattr(rep, 'node'):
                    self._tw.write("[%s] " % rep.node.gateway.id)
                self._tw.write(word, **markup)
                self._tw.write(" " + line)
                self.currentfspath = -2
