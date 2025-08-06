import yaml
import importlib.metadata
from typing import Any
from .magdata import MagData
import click
import os

filters = {entry_point.name: entry_point.load()
           for entry_point in importlib.metadata.entry_points(group="mag_pipeline.filters")}

class MagPipeline:
    def __init__(self, pipeline, **kwargs):
        self.pipeline = dict(pipeline)
        self.pipeline.update(kwargs)

    @classmethod
    def parse(cls, pipeline:str, **kwargs):
        return cls(yaml.safe_load(pipeline), **kwargs)
        
    @classmethod
    def load(cls, path:str, **kwargs):
        with open(path, 'r') as f:
            return cls(yaml.safe_load(f), **kwargs)
        
    def run(self, data: MagData):
        for idx, step in enumerate(self.pipeline["steps"]):
            if isinstance(step, str):
                step_name = step
                kwargs = {}
            else:
                step_name, kwargs = next(iter(step.items()))
            if kwargs:
                params = ", ".join("%s=%s" % (k, v) for k, v in kwargs.items())
                print(f"Running step {idx}: {step_name} with {params}")
            else:
                print(f"Running step {idx}: {step_name}")
            try:
                func = filters[step_name]
            except:
                raise NameError(f"Unknown mag filter {step_name}.")
            new_data = func(self, data, **(kwargs or {}))
            if new_data is not None:
                data = new_data
        return data

    def __repr__(self):
        return yaml.dump(self.pipeline)

@click.command()
@click.argument('pipeline_path', type=click.Path(exists=True))
@click.argument('in_path', type=click.Path(exists=True))
@click.argument('out_path', type=click.Path(), default=".")
@click.option('--verbose', is_flag=True, help='Enable verbose output.')
def main(pipeline_path, in_path, out_path, verbose):
    data = MagData.load(in_path)
    pipeline = MagPipeline.load(pipeline_path, out_path=out_path)
    os.makedirs(out_path, exist_ok=True)
    pipeline.run(data).save(out_path + "/data.mag.zip")
    
if __name__ == "__main__":
    main()
