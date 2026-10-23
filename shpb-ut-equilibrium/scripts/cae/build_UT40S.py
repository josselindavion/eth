# -*- coding: utf-8 -*-
"""
build_UT40S.py -- Construit le banc avec l'eprouvette UT40S, sans modifier build_bench.py.
Abaqus/CAE : File > Run Script... > ce fichier. (Python 2.7 d'Abaqus : execfile existe.)
"""
import os
import sys
import inspect

HERE = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.argv = [os.path.join(HERE, 'build_bench.py'), 'UT40S']     # build_bench.py lit l'eprouvette dans sys.argv
execfile(sys.argv[0], {'__name__': '__main__'})
