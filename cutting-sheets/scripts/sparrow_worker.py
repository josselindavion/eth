# -*- coding: utf-8 -*-
"""
sparrow_worker.py -- Runs one sparrow strip-packing problem in a separate process (started by placement.py).

Why a separate process: sparrow cannot be stopped from Python once started. Running it in its own process lets the
caller kill it as soon as a good enough solution has arrived (for example "the specimens fit on the sheet"), instead
of waiting for the whole time budget.

Protocol: the problem is read as one JSON object on stdin
    {"items": [[id, [[x, y], ...], demand, [angles]], ...], "strip_height": h, "separation": s,
     "seconds": t, "seed": n, "workers": n or null}
and every new best feasible solution is written to stdout as one JSON line
    {"kind": "feasible" | "final", "width": w, "placed": [[id, rotation_deg, tx, ty], ...]}
"""
import json
import sys
import threading


def main():
    import spyrrow
    job = json.loads(sys.stdin.read())
    items = [spyrrow.Item(i, [tuple(p) for p in pts], demand=d, allowed_orientations=a)
             for i, pts, d, a in job['items']]
    inst = spyrrow.StripPackingInstance('plan', strip_height=job['strip_height'], items=items)
    conf = spyrrow.StripPackingConfig(total_computation_time=max(1, int(round(job['seconds']))),
                                      min_items_separation=job['separation'], num_workers=job.get('workers'),
                                      seed=job.get('seed', 1), early_termination=True)
    queue = spyrrow.ProgressQueue()
    box = {}

    def work():
        try:
            box['sol'] = inst.solve(conf, progress=queue)
        except BaseException as e:                          # also the panics of the Rust code
            box['err'] = repr(e)

    def send(kind, sol):
        sys.stdout.write(json.dumps({'kind': kind, 'width': sol.width,
                                     'placed': [[p.id, p.rotation, p.translation[0], p.translation[1]]
                                                for p in sol.placed_items]}) + '\n')
        sys.stdout.flush()

    th = threading.Thread(target=work, daemon=True)
    th.start()
    best = float('inf')
    while th.is_alive():
        th.join(0.1)
        for rtype, sol in queue.drain():
            name = str(rtype)
            if 'Feas' in name and 'Infeas' not in name and sol.width < best - 1e-9:
                best = sol.width
                send('feasible', sol)
    if 'err' in box:
        sys.stdout.write(json.dumps({'kind': 'error', 'error': box['err']}) + '\n')
        sys.stdout.flush()
        return
    send('final', box['sol'])


if __name__ == '__main__':
    main()
