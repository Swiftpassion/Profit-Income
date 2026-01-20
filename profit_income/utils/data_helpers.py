import pandas as pd

def find_header_row(data_io, required_keywords, sheet_name=0):
    data_io.seek(0)
    try:
        preview = pd.read_excel(data_io, sheet_name=sheet_name, header=None, nrows=20, dtype=str)
        best_row_idx = 0
        max_matches = 0
        for i, row in preview.iterrows():
            row_text = " ".join([str(x).lower().strip() for x in row.values if pd.notna(x)])
            matches = sum(1 for k in required_keywords if k.lower() in row_text)
            if matches > max_matches:
                max_matches = matches
                best_row_idx = i
        data_io.seek(0)
        return best_row_idx if max_matches > 0 else 0
    except:
        data_io.seek(0)
        return 0

def get_col_data(df, candidates):
    cols_norm = [" ".join(str(c).replace('\n', ' ').split()).lower() for c in df.columns]
    for cand in candidates:
        cand_clean = " ".join(cand.split()).lower()
        if cand_clean in cols_norm:
            idx = cols_norm.index(cand_clean)
            return df.iloc[:, idx]
    return None
