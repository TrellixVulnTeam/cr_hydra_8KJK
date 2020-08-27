#!/usr/bin/env python
import os
import glob

from setuptools import setup

version_long = '0.1.0.dev0'

# generate entry points
entry_points = {'console_scripts': []}
scripts = [os.path.basename(script)[0:-3] for script in glob.glob('src/*.py')]
for script in scripts:
    print(script)
    entry_points['console_scripts'].append(
        '{0} = {0}:main'.format(script)
    )

print(scripts, entry_points)

if __name__ == '__main__':
    setup(
        name='cr_hydra',
        version=version_long,
        description='CRHydra - distributed CRTomo computing',
        author='Maximilian Weigand',
        author_email='mweigand@geo.uni-bonn.de',
        license='MIT',
        # url='https://github.com/geophysics-ubonn/reda',
        packages=['cr_hydra', ],
        package_dir={
            '': 'src',
            'cr_hydra': 'lib/cr_hydra',
        },
        # install_requires=['numpy', 'scipy', 'pandas', 'matplotlib'],
        py_modules=scripts,
        entry_points=entry_points,
    )
