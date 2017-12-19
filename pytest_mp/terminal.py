from _pytest.terminal import TerminalReporter


# Taken from pytest/_pytest/terminal.py
# and made process safe by avoiding use of `setdefault()`
# Thanks to pytest-concurrent for approach

# Also includes pytest-instafail functionality
# :copyright: (c) 2013-2016 by Janne Vanhala.
# since it isn't compatible w/ MPTerminalReporter


class MPTerminalReporter(TerminalReporter):

    def __init__(self, reporter, manager):
        TerminalReporter.__init__(self, reporter.config)
        self._tw = self.writer = reporter.writer  # some monkeypatching needed to access existing writer
        self.manager = manager
        self.stats = dict()
        self.stat_keys = ['passed', 'failed', 'error', 'skipped', 'warnings', 'xpassed', 'xfailed', '']
        for key in self.stat_keys:
            self.stats[key] = manager.list()
        self.stats_lock = manager.Lock()
        self._progress_items_reported_proxy = manager.Value('i', 0)

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

        # This helps make TerminalReporter process-safe.
        with self.stats_lock:
            if cat in self.stat_keys:
                self.stats[cat].append(rep)
            else:  # not expected and going to be dropped.  TODO: fix this.
                cat_list = self.stats.get(cat, [])
                cat_list.append(rep)
                self.stats[cat] = cat_list

        self._tests_ran = True
        if not letter and not word:
            # probably passed setup/teardown
            return

        # This helps make TerminalReporter process-safe.
        with self.stats_lock:
            self._progress_items_reported_proxy.value += 1

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
                if getattr(self, '_show_progress_info', False):
                    self._tw.write(self._get_progress_information_message() + " ", cyan=True)
                else:
                    self._tw.write(' ')
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

    def _write_progress_if_past_edge(self):
        if not self._show_progress_info:
            return
        last_item = self._progress_items_reported_proxy.value == self._session.testscollected
        if last_item:
            self._write_progress_information_filling_space()
            return

        past_edge = self._tw.chars_on_current_line + self._PROGRESS_LENGTH + 1 >= self._screen_width
        if past_edge:
            msg = self._get_progress_information_message()
            self._tw.write(msg + '\n', cyan=True)

    def _get_progress_information_message(self):
        collected = self._session.testscollected
        if collected:
            progress = self._progress_items_reported_proxy.value * 100 // collected
            return ' [{:3d}%]'.format(progress)
        return ' [100%]'
