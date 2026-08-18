# Platform notebooks

These notebooks are infrastructure steps, not part of every research run.

```text
01_SERVING.py          optional Model/Feature Serving
02_DEPLOY_APP.py       deploy/update the OpenBB API App
03_OPENBB_WORKSPACE.py connect and verify OpenBB Workspace
```

Backtesting, portfolio comparison, Monte Carlo and NVIDIA result review work without running `01_SERVING.py`. Deploy the App when you are ready to view persisted DBO_Quant results in OpenBB Workspace.