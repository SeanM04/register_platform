"""
Custom JSON Encoder for handling pandas data types
"""

import json
import numpy as np
import pandas as pd
from django.core.serializers.json import DjangoJSONEncoder


class PandasJSONEncoder(DjangoJSONEncoder):
    """Custom JSON encoder that handles pandas data types."""
    
    def default(self, obj):
        # Handle pandas specific types
        if hasattr(obj, 'to_dict'):
            return obj.astype(object).to_dict('records')
        elif hasattr(obj, 'item') and not isinstance(obj, int):  # pandas Series but not int
            return obj.astype(object).item()
        elif hasattr(obj, 'values'):  # pandas Index
            return obj.tolist()
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Series):
            return obj.astype(object).tolist()
        elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, int)):
            # Handle other iterables
            try:
                return list(obj)
            except TypeError:
                pass
        
        # Fall back to parent
        return super().default(obj)
