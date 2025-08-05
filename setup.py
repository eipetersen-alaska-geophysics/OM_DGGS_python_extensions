from setuptools import setup, find_packages

setup(
    name="magproc",
    version="0.0.1",
    packages=find_packages(),
    install_requires=[
        "pandas",
        "numpy",
        "click",
    ],
    entry_points={
        'console_scripts': [
            'magproc=magproc.pipeline:main',
        ],
        'mag_pipeline.filters': [
            'all = magproc.magfilters:process_all',
            'write_noise_summary = magproc.magfilters:write_noise_summary',
            'write_diurnal_summary = magproc.magfilters:write_diurnal_summary',
            'write_drape_summary = magproc.magfilters:write_drape_summary',
        ],        
    },
)
