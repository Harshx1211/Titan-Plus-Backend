# Integration Guide - How to Use ML Brain

This guide explains how to integrate the Stage 2 ML components (XGBoost & RL) into your existing trading system.

## Step 1: Replace Old Brain

In your main trading code, replace:
```python
from brain_engine import BrainEngine
brain = BrainEngine(stage=3)
```

With:
```python
from brain_engine_ml import BrainEngineML
brain = BrainEngineML(stage=2)  # Shadow mode
```

## Step 2: Training (One-Time Setup)
Extract historical data and train your first model:
```bash
# Extract data and train
python train_brain.py

# This creates: brain_model.pkl (the trained model)
```

## Step 3: Enable Shadow Mode
Setting `SHADOW_MODE=true` allows you to compare the ML engine's decisions against the original statistical engine without executing real trades.

```python
# In your api.py or main.py
import os
os.environ['SHADOW_MODE'] = 'true'

from shadow_mode import ShadowMode
shadow = ShadowMode()

# During signal evaluation:
confidence, thoughts = shadow.compare_predictions(
    features={'ADX': adx, 'BASIS_RES': basis, 'PCR': pcr, 'OI_RES': oi},
    regime=current_regime
)
```

## Step 4: Monitor Performance
You can monitor the agreement between the two engines by checking `shadow_comparisons.json`.

```bash
# Check shadow comparison results
cat shadow_comparisons.json | jq '.[-10:]'

# View agreement rate
python -c "
import json
data = json.load(open('shadow_comparisons.json'))
agree = sum(1 for d in data if d['agreement'])
print(f'Agreement: {agree/len(data):.1%}')
"
```

## Step 5: Switch to ML (After 30 Days)

Once you are confident in the ML performance:
```python
# Remove shadow mode, use ML directly
from brain_engine_ml import BrainEngineML
brain = BrainEngineML(stage=3)  # Production mode

# Normal usage
decision_id, thoughts = brain.generate_decision(features, regime)
```
