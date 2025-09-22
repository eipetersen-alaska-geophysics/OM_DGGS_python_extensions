import pandas as pd
import re
import importlib.resources

with importlib.resources.files('magproc').joinpath('normalize.csv').open('r') as f:
    normalize = pd.read_csv(f).set_index("variation")["normal"].dropna().to_dict()

def parse(filepath):
    comment_line_pattern = re.compile(r'^\s*[^a-zA-Z0-9_.]')

    header_line = None
    data_start_pos = None

    with open(filepath, 'r', encoding='utf-8') as f:
        while True:
            pos = f.tell()
            line = f.readline()
            if not line:
                break
            if comment_line_pattern.match(line):
                header_line = re.sub(r'^\s*[^a-zA-Z0-9_.]', '', line).strip()
                data_start_pos = f.tell()

    if header_line is None or data_start_pos is None:
        # No comment-style header found — assume standard CSV
        df = pd.read_csv(filepath)
    else:
        # Otherwise, use custom logic
        with open(filepath, 'r', encoding='utf-8') as f:
            f.seek(data_start_pos)
            column_names = [col.strip() for col in header_line.split(',')]
            df = pd.read_csv(f, header=None, names=column_names)

    df = df.rename(columns=normalize)
    
    return df
