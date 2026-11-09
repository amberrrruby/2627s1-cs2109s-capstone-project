# Organize project documentation

> Alright - I have done the project, and now I need to organize the materials I've generated, make a brief write-up (if needed), and check for compliance with AI use.
>
> So, let's roughly build a Markdown write-up file, carry over what we've recorded in `NOTES.md` (polish?), record the structure of this repository, then a section for AI use citation (I'll be downloading chat history as Markdown later). Note that `v2-6.py` is the latest experiment of attempting to pass the last boss level, but failed anyways. Used `v2-5-submit.py` as final submission.
>
> And also mentioning supplementary files, one being the Colab notebok `colab-task-2.ipynb` (`task-2.ipynb` is a local copy), and the two generated model files (one inline `tile_model_loader.py`, one TorchScript `.pt` file).
>
> Also help me make a `.gitignore`.

<details><summary>8 previous messages</summary>

> I’ll inventory the repository and read `NOTES.md` plus any project instructions, then I’ll draft a polished Markdown write-up and a conservative `.gitignore` that keeps submission and supplementary artifacts visible.
>
> <details><summary>Ran a command</summary>
>
> - Ran `Get-ChildItem -Force | Select-Object Mode,Length,LastWriteTime,Name; Write-Output '---FILES---'; rg --files -g '!**/.git/**'; Write-Output '---AGENTS---'; Get-ChildItem -Recurse -Filter AGENTS.md -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName; Write-Output '---STATUS---'; git status --short`
>
> </details>
>
> The repository is currently entirely untracked, so the ignore rules matter: I’ll exclude only reproducible clutter (Python caches and notebook checkpoints), while retaining the datasets/assets, telemetry, experiment history, notebooks, submitted script, and trained model unless you later decide to publish a slimmer archive. I’m now extracting the project narrative and evidence from the notes and source files.
>
> <details><summary>Ran 3 commands</summary>
>
> - Ran `Write-Output '---NOTES---'; Get-Content -Raw NOTES.md; Write-Output '---TASK MARKDOWN---'; Get-Content -Raw task-2-v1-1.md; Write-Output '---ENVIRONMENT---'; Get-Content -Raw environment.yml; Write-Output '---SCRIPT SYMBOLS---'; rg -n "^(class|def) |^#|FINAL|submit|boss|Task|task" v2-5-submit.py v2-6.py tile_model_loader.py utils.py -m 160`
> - Ran `rg -n "^#|^##|^###|Coursemology|v2-5|v2-6|boss|submission|AI|ChatGPT|Codex|Claude" NOTES.md; Write-Output '---NOTES TAIL---'; Get-Content NOTES.md | Select-Object -Skip 150; Write-Output '---NOTEBOOK METADATA---'; $files = 'capstone-project.ipynb','colab-task-2.ipynb','task-2.ipynb','tutorial.ipynb'; foreach ($file in $files) { $json = Get-Content -Raw $file | ConvertFrom-Json; [pscustomobject]@{File=$file; Cells=$json.cells.Count; Kernel=$json.metadata.kernelspec.display_name; Language=$json.metadata.language_info.version} }; Write-Output '---DIR SIZES---'; Get-ChildItem -Directory | ForEach-Object { $sum=(Get-ChildItem $_.FullName -Recurse -File | Measure-Object Length -Sum).Sum; [pscustomobject]@{Directory=$_.Name; Files=(Get-ChildItem $_.FullName -Recurse -File).Count; SizeMB=[math]::Round($sum/1MB,2)} }`
> - Ran `git diff --no-index --stat -- v2-5-submit.py v2-6.py; git diff --no-index --unified=3 -- v2-5-submit.py v2-6.py | Select-Object -First 500; Write-Output '---FILE TYPES AND HASHES---'; Get-FileHash v2-5-submit.py,v2-6.py,colab-task-2.ipynb,task-2.ipynb,tile_model_loader.py,tile_multilabel_cnn_best.torchscript.pt -Algorithm SHA256 | Select-Object Path,Hash`
>
> </details>
>
> I’ve confirmed the final chronology: `v2-5-submit.py` is the submitted agent and passed all Task 2 test sets; `v2-6.py` is a later, unsuccessful boss-level experiment that replaced an expensive large-gem heuristic with a cached MST bound and weighted search. I’ll preserve that distinction prominently so the archive does not imply the experimental file was submitted or successful.
>
> <details><summary>Created 2 files</summary>
>
> - Wrote `./.gitignore` (+37 -0)
> - Wrote `./README.md` (+230 -0)
>
> </details>
>
> The first draft is in place. It treats `NOTES.md` as the detailed engineering log and uses the new README as the polished archive narrative, with explicit final/experimental status, repository map, supplementary artifacts, reproducibility caveats, and an AI-use declaration plus a completion checklist. I’m doing a final consistency check against the actual files and ignore behavior now.
>
> <details><summary>Ran a command</summary>
>
> - Ran `Write-Output '---README HEADINGS---'; rg -n "^#|v2-5-submit|v2-6|0\.9994|Task 3|AI-use" README.md; Write-Output '---IGNORE CHECK---'; git check-ignore -v __pycache__/utils.cpython-313.pyc .ipynb_checkpoints/example.ipynb .pytest_cache/example 2>$null; Write-Output '---ARTIFACTS MUST NOT BE IGNORED---'; $artifacts = 'v2-5-submit.py','v2-6.py','colab-task-2.ipynb','task-2.ipynb','tile_model_loader.py','tile_multilabel_cnn_best.torchscript.pt','telemetry/a1-telemetry.txt','history/v1-0.py'; foreach ($file in $artifacts) { git check-ignore $file 2>$null; if ($LASTEXITCODE -eq 0) { Write-Output "IGNORED: $file" } else { Write-Output "kept: $file" } }; Write-Output '---STATUS---'; git status --short; Write-Output '---DIFF---'; git diff --no-index -- NUL README.md | Select-Object -First 80`
>
> </details>
</details>

Created the project archive documentation and ignore rules:

- [README.md](./README.md) — polished project write-up covering:
  - Task 1 planning approach and version history
  - Task 2 CNN perception pipeline, training, validation, and optimization
  - Recorded results and known limitations
  - `v2-5-submit.py` as the authoritative final submission
  - `v2-6.py` as a later unsuccessful boss-level experiment
  - Repository structure and supplementary artifacts
  - Reproducibility notes
  - AI-use declaration, citation placeholders, and compliance checklist

- [.gitignore](./.gitignore) — excludes:
  - Python bytecode and caches
  - Jupyter checkpoints
  - Testing, type-checking, and coverage caches
  - Local virtual environments and build output
  - Editor and OS clutter

The ignore rules deliberately retain `history/`, `telemetry/`, notebooks, the `.pt` model, and the generated inline model loader.

I left [NOTES.md](./NOTES.md) unchanged as the detailed chronological engineering log; the README carries its important findings in a more polished, submission-friendly form.

Formal AI-policy compliance cannot yet be certified because the course policy is not present in the repository. Once you download the chat histories, place them somewhere like `ai-use/`, replace the citation placeholders in the README, and check the declaration against the course’s required wording.

> ```vbnet
>
> AI Policy
>
> The policy regarding the use of AI varies between courses. For this course:​
>
>     Using AI is permitted as long as proper citations are provided.​
>         If it is possible to share a link to the conversation (e.g., ChatGPT, Bing), then provide the link; if not (e.g., GitHub Copilot), then take screenshots​
>         Document any changes made to the code generated by AI ​
>     It is advisable to use AI-generated code as it is; alteration/obfuscation is strongly discouraged.​
> ```
>
> `\chat-history` will be complete once we've done our work here, then I'll add this thread in as well.
>
> Also include that I did not do any dataset generation - the training data for the Colab notebook used only the provided image assets, and the data augmentation pipelines are fully documented in the notebook.
>
> Cover that in `README.md`, and check for any other missing components required for a proof-of-work submission.

<details><summary>6 previous messages</summary>

> I’ll update the AI-use section against this exact policy, correct the training-data description, and audit `chat-history/` plus the repository for proof-of-work gaps. I’ll keep any still-pending items clearly marked rather than claiming the archive is complete before this thread is added.
>
> <details><summary>Ran 2 commands</summary>
>
> - Ran `Write-Output '---CHAT HISTORY---'; if (Test-Path chat-history) { Get-ChildItem chat-history -Recurse -File | Select-Object Length,LastWriteTime,FullName } else { Write-Output 'chat-history/ not found' }; Write-Output '---TOP LEVEL---'; Get-ChildItem -Force | Select-Object Mode,Length,LastWriteTime,Name; Write-Output '---README AI/TRAINING---'; Get-Content README.md | Select-Object -Skip 80 -First 151; Write-Output '---HISTORY TYPES---'; Get-ChildItem history -File | Sort-Object Name | Select-Object Name,Length; Write-Output '---GITIGNORE---'; Get-Content .gitignore`
> - Ran `Get-ChildItem chat-history -File | Sort-Object Name | ForEach-Object { Write-Output ('--- ' + $_.Name + ' ---'); Get-Content $_.FullName -TotalCount 12 }; Write-Output '--- POSSIBLE LINKS ---'; rg -n "https?://|chatgpt\.com/share|share" chat-history -g '*.md'; Write-Output '--- NOTEBOOK OUTPUT COUNTS ---'; foreach ($file in 'capstone-project.ipynb','colab-task-2.ipynb','task-2.ipynb','tutorial.ipynb') { $j=Get-Content -Raw $file|ConvertFrom-Json; $code=@($j.cells|Where-Object cell_type -eq 'code'); $outputs=($code|ForEach-Object { @($_.outputs).Count }|Measure-Object -Sum).Sum; [pscustomobject]@{File=$file;CodeCells=$code.Count;OutputBlocks=$outputs} | Format-Table -HideTableHeaders }; Write-Output '--- SUBMISSION MODEL MARKERS ---'; rg -n "def get_model|base64|b64decode|optimize_for_inference|DECODER_THRESHOLDS" v2-5-submit.py tile_model_loader.py -m 30`
>
> </details>
>
> The audit found an important policy gap: the 13 exported Markdown conversations are present, but none contains a ChatGPT/Codex share URL. Under the wording you supplied, the Markdown exports are strong supplementary evidence but may not replace share links when sharing is available; otherwise, screenshots are explicitly required. I’ll reflect that as an outstanding action, alongside adding this thread and evidence of the final Coursemology submission/result.
>
> <details><summary>Edited a file, ran 2 commands</summary>
>
> - Ran `Get-ChildItem chat-history -File | Sort-Object Name | Select-Object -ExpandProperty Name; Write-Output '---GIT---'; git rev-parse --is-inside-work-tree; git log --oneline --all -5 2>$null; git status --short`
> - Ran `$n=1; Get-Content README.md | ForEach-Object { '{0,4}: {1}' -f $n, $_; $n++ } | Select-Object -Skip 85`
> - Wrote `./README.md` (+18 -10)
> - Wrote `./README.md` (+11 -6)
> - Wrote `./README.md` (+108 -38)
>
> </details>
>
> The README now includes a concrete modification record for AI-assisted code rather than a generic disclosure. It also distinguishes “no external/independently generated dataset” from the notebook’s on-demand composition and augmentation of supplied assets, which preserves both your intended statement and the actual training procedure.
>
> <details><summary>Ran a command</summary>
>
> - Ran `Write-Output '---DATA PROVENANCE WORDING---'; rg -n "dataset|training input|provided assets|supplied image|synthetic" README.md; Write-Output '---AI/PROOF HEADINGS---'; rg -n "^##|^###|share link|screenshots|required|Outstanding|Git repository" README.md; Write-Output '---LOCAL LINK CHECK---'; $text=Get-Content -Raw README.md; $matches=[regex]::Matches($text,'\[[^\]]+\]\(([^)]+)\)'); $missing=@(); foreach($m in $matches){$target=$m.Groups[1].Value; if($target -notmatch '^(https?://|#)' -and -not (Test-Path -LiteralPath $target)){ $missing += $target }}; if($missing.Count -eq 0){'All local README links resolve.'} else {$missing | Sort-Object -Unique}; Write-Output '---IGNORE/STATUS---'; git check-ignore chat-history/2026-10-08-1716-summarize-grid-adventure-mechanics.md 2>$null; if($LASTEXITCODE -ne 0){'chat-history is retained'}; git status --short`
>
> </details>
</details>

Updated [README.md](./README.md) to reflect the supplied AI policy and the correct training-data provenance.

Key changes:

- States that no external or independently generated dataset was created or used.
- Explains that training examples were formed on demand exclusively from the provided assets in `data/assets/`.
- Points to [colab-task-2.ipynb](./colab-task-2.ipynb) as the complete record of asset selection, layering, train/validation splitting, augmentation, training, calibration, and export.
- Adds `chat-history/` to the repository structure and supplementary-material inventory.
- Links all 13 currently exported conversations individually.
- Records the main changes made across the AI-assisted source versions, including:
  - Task 1 planner iterations
  - Task 2 training pipeline
  - Template matching to batched CNN inference
  - Selective perception replay
  - Telemetry removal and inference optimization
  - Inline model-loader integration
  - The unsuccessful `v2-6.py` boss experiment
  - AI assistance in preparing this archive
- Includes a submission-form AI-use declaration.
- Adds an evidence-based proof-of-work checklist.

The remaining proof-of-work items are now explicitly listed in the README:

1. Export this final conversation into `chat-history/`.
2. Add original conversation share links when sharing is available. If it is not, include the screenshots required by the policy. The Markdown exports alone may not satisfy the policy’s literal wording.
3. Review exported conversations and screenshots for personal information, secrets, or restricted material.
4. Add Coursemology evidence—ideally screenshots or a receipt showing:
   - the submitted filename,
   - submission date,
   - Task 2 results,
   - and the Task 3 boss timeouts.
5. Add your name, student identifier, course term, and submission date where required.
6. Check the assignment’s final file list and upload-size limits.
7. Make an initial Git commit after reviewing everything. The repository currently has no commits and every project file is untracked, so the present chronology comes from `history/`, `NOTES.md`, telemetry, notebooks, and chat records rather than Git history.

I also verified that every local link in the README resolves and that `chat-history/` is retained by [.gitignore](./.gitignore). No commit was created.

> 1. Will do
> 2. Doing share seems to not work - organization restriction?
> 3. Done
> 4. Will do
> 5. Will do
> 6. Should be done
> 7. Will do
>
> Anything else?

<details><summary>2 previous messages</summary>

> I’ll do one last packaging-oriented audit for issues that are easy to miss: embedded credentials, personal machine paths, oversized evidence files, notebook outputs, and whether the final submission can be tied unambiguously to the archived source.
>
> <details><summary>Ran 2 commands</summary>
>
> - Ran `Write-Output '---LARGEST FILES---'; Get-ChildItem -Recurse -File | Where-Object { $_.FullName -notlike '*\.git\*' } | Sort-Object Length -Descending | Select-Object -First 20 @{N='MB';E={[math]::Round($_.Length/1MB,2)}},FullName; Write-Output '---ABSOLUTE USER PATH REFERENCES---'; rg -l -i "C:\\Users\\|/content/drive/|/home/|~/.codex|\.codex/attachments" -g '!*.pt' -g '!data/**' .; Write-Output '---POTENTIAL SECRET FILE NAMES---'; Get-ChildItem -Recurse -File -Force | Where-Object { $_.FullName -notlike '*\.git\*' -and $_.Name -match '(?i)(\.env|credential|secret|token|private[_-]?key|id_rsa|\.pem$|\.p12$)' } | Select-Object -ExpandProperty FullName; Write-Output '---POTENTIAL SECRET ASSIGNMENTS (FILENAMES ONLY)---'; rg -l -i "(api[_-]?key|access[_-]?token|secret[_-]?key|password)\s*[:=]" -g '!*.pt' -g '!data/**' .; Write-Output '---TOTAL SIZE---'; $files=Get-ChildItem -Recurse -File | Where-Object {$_.FullName -notlike '*\.git\*'}; [pscustomobject]@{Files=$files.Count; TotalMB=[math]::Round((($files|Measure-Object Length -Sum).Sum)/1MB,2)}; Write-Output '---FINAL HASH---'; Get-FileHash v2-5-submit.py -Algorithm SHA256 | Select-Object Path,Hash; Write-Output '---MARKDOWN EXPORT SIZES---'; Get-ChildItem chat-history -File | Sort-Object Length -Descending | Select-Object @{N='KB';E={[math]::Round($_.Length/1KB,1)}},Name`
> - Ran `$files = @(Get-ChildItem -Recurse -File | Where-Object { $_.FullName -notlike '*\.git\*' }); Write-Output ("files={0} total_mb={1:N2}" -f $files.Count, (($files | Measure-Object Length -Sum).Sum / 1MB)); $hash=(Get-FileHash v2-5-submit.py -Algorithm SHA256).Hash; Write-Output ("v2-5-submit.py sha256={0}" -f $hash); $chat=Get-ChildItem chat-history -File; Write-Output ("chat_files={0} chat_total_mb={1:N2} largest_chat_kb={2:N1}" -f $chat.Count,(($chat|Measure-Object Length -Sum).Sum/1MB),(($chat|Sort-Object Length -Descending|Select-Object -First 1).Length/1KB)); Write-Output 'tracked_files:'; git ls-files | Measure-Object | Select-Object -ExpandProperty Count`
>
> </details>
</details>

Nothing fundamental appears missing. The archive is already strong proof of work.

A few final safeguards:

- If organization restrictions prevent share links, screenshots are the policy-approved fallback. Keep the Markdown exports too. Ideally, each screenshot set should show the conversation title/date and enough prompt-response context to identify what assistance was provided.
- Preserve evidence that `v2-5-submit.py` is exactly the submitted file. Its current SHA-256 is:

  ```text
  9B2D2E8C3DCE045D4AC0D40C5D0BFF434B2E1764FC3ACD63E73B38EFF8A3597E
  ```

  If Coursemology lets you download the submitted source, compare its hash with this one. Otherwise, retain a screenshot showing the submitted filename/code.
- The archive is currently about 20.26 MB across 451 files. That is reasonable, but verify the actual upload limit rather than relying on the contents looking small enough.
- When creating the final archive, exclude ignored clutter such as `__pycache__/` and `.ipynb_checkpoints/`. After committing, `git archive` is a clean way to package only tracked files.
- If this repository will be published publicly rather than submitted privately, confirm that redistributing the supplied assets, tutorial notebook, public-level definitions, and course utilities is permitted. For a private proof-of-work submission, retaining them is useful.
- Keep notebook outputs intact—they provide valuable training and evaluation evidence.
- After adding this conversation and the Coursemology screenshots, make the commit and preferably tag it with something unambiguous such as `proof-of-work-final`.

I also checked for obvious credential files, secret assignments, and personal absolute machine paths; none were detected. The 13 existing chat exports total only about 0.48 MB. The one remaining technical fact is that Git currently tracks zero files, so the initial commit is important.
