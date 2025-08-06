from setuptools import setup, find_packages

setup(
    name="magproc",
    version="0.0.1",
    packages=find_packages(),
    install_requires=[
        "pandas",
        "numpy",
        "click",
        "geopandas",
        "contextily",
        "scipy",
        "pyproj"
    ],
    entry_points={
        'console_scripts': [
            'magproc=magproc.pipeline:main',
        ],
        'mag_pipeline.filters': [
            'set_constants = magproc.magfilters:set_constants',
            'diurnal_qc_for_15s_chord = magproc.magfilters:diurnal_qc_for_15s_chord',
            'diurnal_qc_for_60s_chord = magproc.magfilters:diurnal_qc_for_60s_chord',
            'drape_and_speed_qc = magproc.magfilters:drape_and_speed_qc',
            'noice_qc = magproc.magfilters:noice_qc',
            'write_noise_summary = magproc.magfilters:write_noise_summary',
            'write_diurnal_summary = magproc.magfilters:write_diurnal_summary',
            'write_drape_summary = magproc.magfilters:write_drape_summary',            
            'set_meta = magproc.magfilters:set_meta',
            'lowpass_filter_butterworth = magproc.magfilters:lowpass_filter_butterworth',
            'highpass_filter_butterworth = magproc.magfilters:highpass_filter_butterworth',
            'bandpass_filter_butterworth = magproc.magfilters:bandpass_filter_butterworth',
            'downline_distance = magproc.magfilters:downline_distance',
        ],        
    },
)
