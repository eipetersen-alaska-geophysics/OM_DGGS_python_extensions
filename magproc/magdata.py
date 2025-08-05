import pandas as pd
import yaml
import zipfile
from io import BytesIO, StringIO
from typing import Dict


class MagData:
    def __init__(self, data: pd.DataFrame, **meta):
        self.data = data
        self.meta = meta

    @classmethod
    def load(cls, path: str):
        """Load mag data from file. Filename should end in .mag.zip or .csv"""
        if path.endswith(".csv"):
            with open(path) as f:
                df = pd.read_csv(f)
                meta = {}
        else:
            with zipfile.ZipFile(path, 'r') as z:
                with z.open("data.csv") as f:
                    df = pd.read_csv(f)
                with z.open("meta.yaml") as f:
                    meta = yaml.safe_load(f)
        return cls(df.set_index(["Line", "FIDCOUNT"]), **meta)

    def save(self, path: str):
        """Save mag data to file. Filename should end in .mag.zip"""
        with zipfile.ZipFile(path, 'w') as z:
            csv_buffer = StringIO()
            self.data.reset_index(drop=True).to_csv(csv_buffer, index=False)
            z.writestr("data.csv", csv_buffer.getvalue())
            z.writestr("meta.yaml", yaml.dump(self.meta))

    def __repr__(self):
        return f"""{yaml.dump(self.meta)}

        {self.data.describe().T}"""
