services:
  - type: web
    name: thermogram-markup-service
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
```
