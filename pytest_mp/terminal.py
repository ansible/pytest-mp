from _pytest.terminal import TerminalReporter

from pytest_mp.plugin import manager


# Taken from pytest/_pytest/terminal.py
# and made process safe by avoiding use of `setdefault()`
# Thanks to pytest-concurrent for approach

# Also includes pytest-instafail functionality
# :copyright: (c) 2013-2016 by Janne Vanhala.
# since it isn't compatible w/ MPTerminalReporter


class MPTerminalReporter(TerminalReporter):

    def __init__(self, reporter):
        TerminalReporter.__init__(self, reporter.config)
        self._tw = self.writer = reporter.writer  # some monkeypatching needed to access existing writer
        self.stats = manager.dict()
        self.stats_lock = manager.Lock()

    def pytest_collectreport(self, report):
        # Show errors occurred during the collection instantly.
        TerminalReporter.pytest_collectreport(self, report)
        if self.config.option.instafail:
            if report.failed:
                if self.isatty:
                    self.rewrite('')  # erase the "collecting"/"collected" message
                self.print_failure(report)

    def summary_failures(self):
        if not self.config.option.instafail:
            TerminalReporter.summary_failures(self)

    def summary_errors(self):
        if not self.config.option.instafail:
            TerminalReporter.summary_errors(self)

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

        if self.config.option.instafail and report.failed and not hasattr(report, 'wasxfail'):
            if self.verbosity <= 0:
                self._tw.line()
            self.print_failure(report)

    def print_failure(self, report):
        if self.config.option.tbstyle != "no":
            if self.config.option.tbstyle == "line":
                line = self._getcrashline(report)
                self.write_line(line)
            else:
                msg = self._getfailureheadline(report)
                if not hasattr(report, 'when'):
                    msg = "ERROR collecting " + msg
                elif report.when == "setup":
                    msg = "ERROR at setup of " + msg
                elif report.when == "teardown":
                    msg = "ERROR at teardown of " + msg
                self.write_sep("_", msg)
                if not self.config.getvalue("usepdb"):
                    self._outrep_summary(report)
