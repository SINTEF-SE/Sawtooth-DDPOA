from setuptools import setup, find_packages

setup(name='sawtooth-ddpoa-consensus',
      version="0.1",
      description='Sawtooth DDPoA Consensus Module',
      author='SINTEF',
      url='TBD',
      packages=find_packages(),
      install_requires=[
          'requests',
          'sawtooth-sdk',
          'protobuf == 3.20.1',
          'STVPoll == 0.2.0'
      ],
      entry_points={})
