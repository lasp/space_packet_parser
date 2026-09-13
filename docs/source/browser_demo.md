# In-Browser Demo

The demo below runs Space Packet Parser entirely in your browser using
[Pyodide](https://pyodide.org/) (a WebAssembly build of Python). Select a binary CCSDS packet file
and an XTCE definition file, and it will parse the packets locally — no data is sent to a server.

```{eval-rst}
.. raw:: html

   <iframe src="_static/browser-parsing.html"
           title="Space Packet Parser in-browser demo"
           loading="lazy"
           style="width: 100%; height: 620px; border: 1px solid #e1e4e5; border-radius: 4px;">
   </iframe>
```
