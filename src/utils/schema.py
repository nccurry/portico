import pandas as pd
import pandera as pa
from pandera.typing import Index, DataFrame, Series


class TillerRawSchema(pa.DataFrameModel):
    Date: Series[str] = pa.Field(gt=2000, coerce=True)
    month: Series[int] = pa.Field(ge=1, le=12, coerce=True)
    day: Series[int] = pa.Field(ge=0, le=365, coerce=True)