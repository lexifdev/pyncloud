from distutils.core import setup


setup(
    name='pyncloud',
    packages=['pyncloud'],
    version='0.0.3',
    description='Simple python library for Naver Cloud (https://cloud.naver.com).',
    long_description='WIP',
    license='MIT License',
    author='Sl Kim',
    author_email='sl@lxf.kr',
    url='https://github.com/lexifdev/pyncloud',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'License :: OSI Approved :: MIT License',
    ],
    install_requires=[
        'rsa',
        'requests',
    ]
)
