#!/usr/bin/env python
from distutils.core import setup,Extension
import sys

setup(
  name='PolyXSim',
  version='0.9.0',
  description='Image viewer for file series of diffraction images',
  license='GPL', maintainer='Henning Osholm Soerensen',
  maintainer_email='henning.sorensen@risoe.dk',
  url='http://fable.wiki.sourceforge.net',
  packages=['polyxsim'],
  package_dir={"polyxsim": "polyxsim"},
  scripts=["scripts/PolyXSim.py"]
)
