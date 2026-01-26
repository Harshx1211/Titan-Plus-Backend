from growwapi import GrowwAPI
import inspect

print("GrowwAPI Signature:")
print(inspect.signature(GrowwAPI.__init__))
print("\nMethods in GrowwAPI:")
for m in dir(GrowwAPI):
    if not m.startswith('_'):
        print(f" - {m}")
