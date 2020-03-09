#!/usr/bin/env python
from setuptools import setup

setup(name = "tangods-merlin",
      version = "0.0.1",
      description = ("Tango device server for the Merlin detector."),
      author = "Alexander Bjoerling, Clemens Weninger",
      author_email = "alexander.bjorling@maxiv.lu.se",
      license = "GPLv3",
      url = "http://www.maxiv.lu.se",
      packages = ['merlinlib'],
      package_dir = {'':'.'},
      scripts = ['merlinds']
     )
