# -*- coding: utf-8 -*-
"""
progress.py -- Numbered steps and progress bar in the terminal (no dependency).

    step(3, 6, 'Placement')          ->  [3/6] Placement
    bar = Bar('Sheet 1', 60)         ->      Sheet 1        [#########-----------]  45 %  27/60  ~33 s left
    bar.update(27) ... bar.done()    ->      Sheet 1        [####################] 100 %  60/60  in 1 min 00 s
"""
import shutil
import sys
import time

WIDTH = 20


def _fmt(sec):
    sec = int(round(sec))
    if sec < 60:
        return '%d s' % sec
    if sec < 3600:
        return '%d min %02d s' % (sec // 60, sec % 60)
    return '%d h %02d min' % (sec // 3600, (sec % 3600) // 60)


def step(k, n, label):
    print('[%d/%d] %s' % (k, n, label), flush=True)


class Bar:
    """Progress bar on one line (refreshed at most every 0.2 s)."""

    def __init__(self, label, total):
        self.label, self.total = label, max(1, total)
        self.t0 = self.last = time.time()
        self.n, self.info = 0, ''
        self._draw(0, force=True)

    def _line(self, n, tail):
        f = min(1.0, n / self.total)
        k = int(round(f * WIDTH))
        return '    %-14s [%s%s] %3d %%  %*d/%d  %s' % (self.label, '#' * k, '-' * (WIDTH - k), round(100 * f),
                                                     len(str(self.total)), n, self.total, tail)

    def _draw(self, n, force=False):
        now = time.time()
        if not force and now - self.last < 0.2:
            return
        self.last = now
        el = now - self.t0
        tail = ('~%s left' % _fmt(el / n * (self.total - n))) if 0 < n < self.total and el > 1 else ''
        tail = ('%s   %s' % (tail, self.info)).strip()
        # never wider than the terminal: otherwise the line wraps and the carriage return no longer erases it
        cols = shutil.get_terminal_size((80, 24)).columns - 1
        sys.stdout.write('\r' + self._line(n, tail)[:cols].ljust(cols))
        sys.stdout.flush()

    def update(self, n, info=''):
        self.n, self.info = n, info
        self._draw(n)

    def done(self, note=''):
        el = time.time() - self.t0
        cols = shutil.get_terminal_size((80, 24)).columns - 1
        sys.stdout.write('\r' + ' ' * cols + '\r' + self._line(self.total, ('in %s   %s' % (_fmt(el), self.info)).strip())
                         + '\n')
        if note:
            sys.stdout.write('    %s\n' % note)
        sys.stdout.flush()
