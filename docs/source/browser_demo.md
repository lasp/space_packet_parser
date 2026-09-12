# In-Browser Demo

The demo below runs Space Packet Parser entirely in your browser using
[Pyodide](https://pyodide.org/) (a WebAssembly build of Python). Select a binary CCSDS packet file
and an XTCE definition file, and it will parse the packets locally — no data is sent to a server.

```{eval-rst}
.. raw:: html
   :file: _static/browser-parsing.html
```
