# Modal Demo

A minimal NOPZ demo: a web page with a button that opens a modal dialog.

## Run it

```bash
uv run nopz demos/modal/modal.py --output ./demos/modal/runs/test1
```

The agent will create an `index.html` that satisfies all 7 regulations. Open the resulting `index.html` in a browser to verify the modal works.

## Regulations

1. `index_exists` — entry point exists
2. `has_button` — page has a `<button>` element
3. `has_modal` — page has a modal/dialog element
4. `button_opens_modal` — button click opens the modal
5. `modal_closes` — modal can be closed
6. `proper_structure` — uses semantic HTML (`<dialog>` or `role="dialog"`)
7. `styled` — has CSS styling for the modal
