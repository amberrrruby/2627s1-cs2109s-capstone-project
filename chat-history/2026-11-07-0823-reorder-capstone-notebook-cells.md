# Reorder capstone notebook cells

> Can you reorganize `capstone-project.ipynb` so it's more tidy? Particularly, there are `Agent` definition cells littered around. And I often have to scroll for half a minute to get to the cell I want - maybe move the text cells below, and all the code cells above? Keep the task-1 telemetry cell and the task-2 telemetry cell however, just reorder so I don't need to scroll.

<details><summary>4 previous messages</summary>

> I’ll inspect the notebook and group the code cells into a clearer order, keeping both telemetry cells and moving explanatory text below.
>
> <details><summary>Ran 3 commands</summary>
>
> - Ran `Get-Location; rg --files -g AGENTS.md -g '*capstone-project.ipynb' -g '*ipynb*'`
> - Ran `@'
> import json
> from pathlib import Path
> p=Path('capstone-project.ipynb')
> n=json.loads(p.read_text(encoding='utf-8'))
> for i,c in enumerate(n['cells']):
>  s=''.join(c.get('source',[]))
>  lines=s.splitlines()
>  print(f'{i:3} {c["cell_type"]:8} {len(lines):4} lines id={c.get("id", "")} | '+ ' | '.join(lines[:3])[:230])
>  if c['cell_type']=='code':
>   import ast
>   try:
>    a=ast.parse(s)
>    print('    defs: '+', '.join(x.name for x in a.body if isinstance(x,(ast.FunctionDef,ast.ClassDef,ast.AsyncFunctionDef))))
>   except SyntaxError: pass
> '@ | python -`
> - Ran `@'
> import json
> from pathlib import Path
> n=json.loads(Path('capstone-project.ipynb').read_text(encoding='utf-8'))
> for i in [6,8,12,13,19]:
>  c=n['cells'][i]; s=''.join(c['source'])
>  print('\nCELL',i,'METADATA',c['metadata'])
>  print(s[:6500] if i!=12 else s[:4200])
> '@ | python -
> git status --short`
>
> </details>
>
> There are two `Agent` definitions, including an 1,843-line version with telemetry. I’ll place them together at the top, with the telemetry-enabled version last so it remains active, then the evaluation helpers and both telemetry cells. I’ll collapse the long definitions by default and move all explanatory text to the bottom.
>
> <details><summary>Ran a command</summary>
>
> - Ran `@'
> import ast
> import copy
> import json
> from pathlib import Path
>
> path = Path('capstone-project.ipynb')
> original = json.loads(path.read_text(encoding='utf-8'))
> notebook = copy.deepcopy(original)
> cells = notebook['cells']
> # Setup, telemetry, public checks, observation previews, then model examples.
> code_order = [6, 12, 8, 13, 19, 14, 20, 22, 24, 26, 11, 16, 18,
>               29, 31, 33, 35, 37, 39, 41, 43, 45, 47]
> assert set(code_order) == {i for i,c in enumerate(cells) if c['cell_type'] == 'code'}
> labels = {
>     6: 'Earlier Agent definition',
>     12: 'Active Agent - planning and perception telemetry',
>     8: 'Public evaluation helpers',
>     13: 'Task 1 telemetry - GridState',
>     19: 'Task 2 telemetry - image observation',
> }
> for i, label in labels.items():
>     cells[i]['metadata']['name'] = label
> for i in [6, 12, 8]:
>     cells[i]['metadata'].setdefault('jupyter', {})['source_hidden'] = True
> notebook['cells'] = [cells[i] for i in code_order] + [c for c in cells if c['cell_type'] != 'code']
>
> # Reordering must preserve every source, result, execution count, and cell ID.
> assert len(notebook['cells']) == len(original['cells'])
> by_id = {c['id']: c for c in original['cells']}
> for cell in notebook['cells']:
>     before = by_id[cell['id']]
>     assert {k:v for k,v in cell.items() if k != 'metadata'} == {k:v for k,v in before.items() if k != 'metadata'}
>     if cell['cell_type'] == 'code':
>         ast.parse(''.join(cell['source']))
> for i in [13, 19]:
>     assert next(c for c in notebook['cells'] if c['id'] == original['cells'][i]['id'])['source'] == original['cells'][i]['source']
> try:
>     import nbformat
> except ImportError:
>     print('nbformat unavailable; JSON, cell preservation, and Python syntax checks passed.')
> else:
>     nbformat.validate(notebook)
>     print('Notebook schema, cell preservation, and Python syntax checks passed.')
> path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
> assert json.loads(path.read_text(encoding='utf-8')) == notebook
> print(f'Saved {len(code_order)} code cells followed by {len(cells)-len(code_order)} text cells.')
> print('Both telemetry cells retained; all cell sources and saved outputs unchanged.')
> '@ | python -`
>
> </details>
</details>

Reorganized [capstone-project.ipynb](./capstone-project.ipynb):

- Grouped both `Agent` definitions at the top, collapsed by default.
- Placed both telemetry cells directly after evaluation helpers.
- Moved all explanatory text below the code.

All code and saved outputs are preserved. JSON and Python syntax checks passed; cells weren’t rerun.
