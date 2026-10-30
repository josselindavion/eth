# -*- coding: utf-8 -*-
"""
progress.py -- Etapes numerotees et barre de progression dans le terminal (sans dependance).

    step(3, 6, 'Placement')          ->  [3/6] Placement
    bar = Bar('Recuit', 120)         ->      Recuit         [#########-----------]  45 %   54/120  reste ~1 min 10 s
    bar.update(54) ... bar.done()    ->      Recuit         [####################] 100 %  120/120  en 2 min 30 s
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
    """Barre de progression sur une ligne (rafraichie au plus toutes les 0,2 s)."""

    def __init__(self, label, total):
        self.label, self.total = label, max(1, total)
        self.t0 = self.last = time.time()
        self.n = 0
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
        tail = ('reste ~%s' % _fmt(el / n * (self.total - n))) if 0 < n < self.total and el > 1 else ''
        # jamais plus large que le terminal : sinon la ligne passe a la ligne et le retour chariot ne l'efface plus
        cols = shutil.get_terminal_size((80, 24)).columns - 1
        sys.stdout.write('\r' + self._line(n, tail)[:cols].ljust(cols))
        sys.stdout.flush()

    def update(self, n):
        self.n = n
        self._draw(n)

    def done(self, note=''):
        el = time.time() - self.t0
        cols = shutil.get_terminal_size((80, 24)).columns - 1
        sys.stdout.write('\r' + ' ' * cols + '\r' + self._line(self.total, 'en %s' % _fmt(el)) + '\n')
        if note:
            sys.stdout.write('    %s\n' % note)
        sys.stdout.flush()
