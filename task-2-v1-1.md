# Task 2 — Dataset and CNN walkthrough

This document explains the code added after the initial Colab setup in `task-2.ipynb`. The notebook is building a **per-tile, multi-label image classifier**. Its input is one RGBA board tile; its output says which game entities are visible in that tile. Later, the agent will run that model over every board tile and rebuild a `GridState` for the existing Task 1 planner.

The pipeline is:

```text
source sprites
  -> held-out asset split
  -> synthetic composited tiles + visual augmentation
  -> (RGBA tensor, multi-label target)
  -> compact CNN
  -> per-label probabilities
  -> calibrated labels and reconstructed board
```

## 1. Asset-level training / validation split

```python
VAL_FRACTION = 0.20
SPLIT_RNG = random.Random(SEED)

asset_paths = {
    label: sorted((ASSETS / ASSET_NAME[label]).glob("*.png"))
    for label in LABELS
}

for label, paths in asset_paths.items():
    paths = paths.copy()
    SPLIT_RNG.shuffle(paths)
    val_count = max(1, round(len(paths) * VAL_FRACTION))
    val_assets[label] = paths[:val_count]
    train_assets[label] = paths[val_count:]
```

This splits **the original sprite files**, not generated images. For each semantic class, roughly 20% of its PNG variants are reserved for validation. A sprite appearing in `val_assets` never appears in `train_assets`.

That matters because the requirement is visual generalization. If validation were instead a random split of generated images, the same underlying sprite could be present in both sets with different brightness or noise. The model could then memorize the sprite rather than learn the entity category.

```python
assert not set(train_assets[label]) & set(val_assets[label])
assert train_assets[label]
```

These checks reject an accidental overlap and make sure the validation split did not consume every example of a small class.

## 2. Labels and layer semantics

```python
LABELS = (
    "floor", "wall", "lava", "exit", "locked", "opened", "box",
    "agent", "gem", "coin", "key", "boots", "ghost", "shield",
)

target = torch.zeros(len(LABELS), dtype=torch.float32)
```

The target is a vector of 14 independent binary values—not one single class number. For example:

| Visible tile | Positive labels |
| --- | --- |
| Bare floor | `floor` |
| A wall | `wall` |
| A gem | `gem` |
| Agent on a gem | `agent`, `gem` |
| Agent on exit | `agent`, `exit` |

`floor` is deliberately an **empty-tile sentinel**. It is `1` only when nothing else is visible. It is not marked as positive behind every sprite, even though a floor texture is used visually as the background. This lets the model distinguish a genuinely empty cell from a cell containing one or more entities.

## 3. Loading sprite images safely

```python
@lru_cache(maxsize=None)
def load_rgba(path_string):
    with Image.open(path_string) as image:
        return image.convert("RGBA").copy()

def choose_asset(asset_dict, label, rng):
    return load_rgba(str(rng.choice(asset_dict[label]))).copy()
```

`load_rgba` reads an asset as RGBA, preserving transparency. The cache avoids repeatedly reopening the same Drive PNG during a training run. `choose_asset` makes a copy before returning it, so later resize/compositing operations cannot alter the cached original.

## 4. Compositing a semantic tile

```python
background = choose_asset(self.asset_dict, "floor", rng)
image = background.resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.LANCZOS)

for label in layers:
    target[LABEL_TO_INDEX[label]] = 1.0
    overlay = choose_asset(self.asset_dict, label, rng)
    overlay = overlay.resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.LANCZOS)
    image = Image.alpha_composite(image, overlay)
```

Every synthetic tile starts with a randomly selected floor sprite. Each semantic layer is then alpha-composited onto it, which respects transparent pixels in an entity sprite. A gem, for example, remains visible over the floor; an agent is composited last when it shares a cell with an item or exit.

```python
primary = rng.choice(PRIMARY_LABELS)
layers = [] if primary == "floor" else [primary]

if primary == "floor" and rng.random() < 0.35:
    layers.append("agent")
elif primary in AGENT_BASE_LABELS and rng.random() < 0.35:
    layers.append("agent")
```

This selects a bare floor or one primary entity. On eligible tiles, it sometimes places the agent over the primary entity. This deliberately produces both simple cases and the layered cases a softmax classifier could not represent.

`PRIMARY_LABELS` excludes `agent` because an agent is always handled as an overlay. It can therefore appear on a bare floor, exit, gem, coin, key, boots, ghost, or shield.

## 5. Visual augmentation

```python
scaled = image.resize((68, 68), Image.Resampling.BICUBIC)
left, top = rng.randrange(5), rng.randrange(5)
image = scaled.crop((left, top, left + IMAGE_SIZE, top + IMAGE_SIZE))
```

This applies a very small zoom and crop. It simulates small renderer or capture alignment changes while retaining the same visible entity semantics.

```python
rgb, alpha = image.convert("RGB"), image.getchannel("A")
rgb = ImageEnhance.Brightness(rgb).enhance(rng.uniform(0.85, 1.15))
rgb = ImageEnhance.Contrast(rgb).enhance(rng.uniform(0.85, 1.15))
rgb = ImageEnhance.Color(rgb).enhance(rng.uniform(0.85, 1.15))
```

Brightness, contrast, and colour saturation change only how the image looks. The alpha channel is retained separately so colour manipulation does not damage transparency.

```python
if rng.random() < 0.30:
    rgb = rgb.filter(ImageFilter.GaussianBlur(rng.uniform(0.15, 0.65)))

if rng.random() < 0.30:
    rgb.save(buffer, format="JPEG", quality=rng.randint(72, 95))
```

Some training samples get a mild blur or JPEG encode/decode cycle. These model common visual degradation while preserving the label. JPEG is applied to RGB only; the original alpha channel is restored afterwards.

```python
noise = np.asarray(
    [rng.gauss(0.0, 2.0) for _ in range(pixels.size)], dtype=np.float32
).reshape(pixels.shape)
pixels = np.clip(pixels + noise, 0, 255).astype(np.uint8)
```

This adds low-amplitude Gaussian pixel noise, then clamps values back into the valid image range. It is intentionally subtle: the goal is robustness, not turning sprites into unrelated images.

## 6. The PyTorch dataset

```python
class SyntheticTileDataset(Dataset):
    def __init__(self, asset_dict, count, *, augment, seed):
        self.asset_dict = asset_dict
        self.count = count
        self.augment = augment
        self.seed = seed

    def __getitem__(self, index):
        epoch = getattr(self, "epoch", 0)
        rng = random.Random(self.seed + index + epoch * self.count)
        ...
        return tensor, target
```

A PyTorch `Dataset` does not hold 24,000 pre-rendered images. Instead, it creates one deterministic synthetic image when the data loader asks for a given index.

```python
train_dataset.set_epoch(epoch)
```

Before each training epoch, changing `epoch` changes the random seed used for every index. The model therefore sees fresh asset combinations and augmentations in the next epoch, while still drawing only from `train_assets`.

```python
array = np.ascontiguousarray(np.asarray(image, dtype=np.float32) / 255.0)
tensor = torch.from_numpy(array).permute(2, 0, 1)
```

This converts a Pillow image from `H × W × 4` values in the integer range 0–255 to a PyTorch tensor shaped `4 × H × W` with floating-point values from 0–1. PyTorch convolution layers expect channels first, hence `permute(2, 0, 1)`.

```python
train_dataset = SyntheticTileDataset(train_assets, 24_000, augment=True, seed=SEED)
val_dataset = SyntheticTileDataset(val_assets, 6_000, augment=False, seed=SEED + 1_000_000)
```

Training uses augmentation; validation intentionally does not. Validation is therefore repeatable and answers a focused question: can the model recognize held-out sprite variants without relying on visual perturbations?

## 7. Data loaders

```python
train_loader = DataLoader(
    train_dataset, batch_size=128, shuffle=True,
    num_workers=NUM_WORKERS, pin_memory=(DEVICE.type == "cuda"),
)
```

The data loader groups 128 generated tiles into a batch and shuffles their order. On a GPU runtime, two worker processes prepare samples in parallel and pinned memory makes host-to-GPU transfers quicker. The validation loader has the same batching but does not shuffle because its order is irrelevant and stable.

Workers are deliberately not persistent. New workers see the new `dataset.epoch` value at the start of the next epoch, so they generate a fresh training set rather than continuing to use the prior epoch's state.

## 8. CNN architecture

```python
class TileMultiLabelCNN(nn.Module):
    def __init__(self, num_labels=len(LABELS)):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(4, 32, 3, padding=1),
            nn.BatchNorm2d(32), nn.ReLU(inplace=True), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.BatchNorm2d(64), nn.ReLU(inplace=True), nn.MaxPool2d(2),
            nn.Conv2d(64, 96, 3, padding=1),
            nn.BatchNorm2d(96), nn.ReLU(inplace=True), nn.MaxPool2d(2),
            nn.Conv2d(96, 128, 3, padding=1),
            nn.BatchNorm2d(128), nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d(1),
        )
        self.classifier = nn.Linear(128, num_labels)
```

The network starts with four input channels because the images are RGBA, not RGB. The convolution blocks gradually increase the number of learned feature channels from 32 to 128. Each max-pooling layer reduces spatial resolution, allowing later layers to reason about larger visual patterns.

`BatchNorm2d` stabilizes training by normalizing intermediate activations; `ReLU` supplies non-linearity. `AdaptiveAvgPool2d(1)` converts any final spatial map into one value per feature channel, so the classifier receives 128 learned summary features for each tile.

```python
def forward(self, x):
    return self.classifier(self.features(x).flatten(1))
```

The final linear layer returns 14 **logits**—unbounded real numbers, one per label. It does not apply a sigmoid itself because the training loss below expects raw logits for better numerical stability.

The model has about 185,000 parameters. That is small enough to meet the eventual CPU inference and embedded-model constraints while retaining enough capacity for visual variants.

## 9. Multi-label loss and optimizer

```python
criterion = nn.BCEWithLogitsLoss()
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
```

`BCEWithLogitsLoss` applies a sigmoid internally and calculates a separate binary cross-entropy loss for each of the 14 labels. That is the appropriate objective when `agent + gem` can both be true. A softmax/cross-entropy setup would wrongly force exactly one label to win.

AdamW is a practical adaptive optimizer. `weight_decay` lightly discourages unnecessarily large weights. The cosine scheduler gradually reduces the learning rate over the 15 epochs, allowing larger early corrections and finer later adjustments.

## 10. Training one epoch

```python
for images, targets in train_loader:
    images = images.to(DEVICE, non_blocking=True)
    targets = targets.to(DEVICE, non_blocking=True)
    optimizer.zero_grad(set_to_none=True)
    loss = criterion(model(images), targets)
    loss.backward()
    optimizer.step()
```

For each batch, the model predicts logits, compares them to the multi-label targets, and calculates a loss. `backward()` computes the gradients that say how each parameter affected that loss. `step()` updates the parameters in the direction that should reduce it next time.

The targets are sent to the same CPU/GPU device as the model. `non_blocking=True` can overlap copies with computation when pinned GPU memory is available.

## 11. Validation metrics

```python
predictions = torch.sigmoid(logits) >= 0.5
expected = targets.bool()
true_positive += (predictions & expected).sum(0).cpu()
false_positive += (predictions & ~expected).sum(0).cpu()
false_negative += (~predictions & expected).sum(0).cpu()
```

During validation, each logit is converted to a probability with sigmoid. The initial decision threshold is 0.5. For every label independently, the notebook counts true positives, false positives, and false negatives across all validation tiles.

```python
precision = true_positive / (true_positive + false_positive)
recall = true_positive / (true_positive + false_negative)
f1 = 2 * precision * recall / (precision + recall)
```

Precision answers: “When the model says this entity is present, how often is it right?” Recall answers: “Of all cells with this entity, how many did it find?” F1 balances both. Per-class metrics are more useful than a single accuracy score because rare entities and layered cases can otherwise disappear into an average.

## 12. Best checkpoint selection

```python
if macro_f1 > best_macro_f1:
    torch.save({
        "state_dict": model.state_dict(),
        "labels": LABELS,
        "image_size": IMAGE_SIZE,
        "epoch": epoch + 1,
        "macro_f1": macro_f1,
    }, BEST_CHECKPOINT)
```

The notebook keeps the model state from the epoch with the highest mean F1 across the 14 labels. It saves the weights, label order, image resolution, epoch, and score to Drive. The label order is stored because output index 7 is meaningful only if the submission-side decoder knows it maps to `agent`.

```python
best_checkpoint = torch.load(BEST_CHECKPOINT, map_location=DEVICE)
model.load_state_dict(best_checkpoint["state_dict"])
_, precision, recall, f1 = evaluate(val_loader)
```

At the end, the code reloads the best checkpoint before reporting final per-label metrics. That avoids accidentally presenting metrics from a final epoch that performed worse than an earlier one.

## Progress snapshot — training and calibration complete

The first training run completed all 15 epochs. The held-out asset-variant results improved from macro-F1 `0.9474` in epoch 1 to `0.9994` in epoch 15; the selected checkpoint is:

```text
/content/drive/MyDrive/Colab Notebooks/checkpoints/tile_multilabel_cnn_best.pt
```

At the default 0.5 decision threshold, only 7 of 6,000 held-out synthetic tiles had any label error (`0.117%`). They were concentrated in one visual ambiguity: agent-on-gem variants that resembled ghost variants.

```text
False positives: ghost = 7
False negatives: gem = 1
```

This is small numerically but meaningful for planning: the combined failure can reconstruct an `agent + gem` tile as `agent + ghost`, omitting a mandatory gem from the inferred state.

### Locked decoder thresholds

The validation threshold sweep reached zero label errors, but its general “choose the largest threshold on an F1 tie” rule often returned 0.95 for classes that were already perfect at 0.5. Those high values are not evidence-based and could reduce tolerance for unseen artwork.

The submission decoder should therefore keep the standard 0.5 threshold except for the two labels supported by observed failures:

```python
DECODER_THRESHOLDS = {label: 0.50 for label in LABELS}
DECODER_THRESHOLDS.update({
    "gem": 0.40,    # recovers the only held-out gem false negative
    "ghost": 0.90,  # above the worst ghost false positive (0.842)
})
```

On the held-out validation set, this conservative policy gives `0 / 6000` tiles with any label error. The next checkpoint is to export and independently reload the trained CNN as an inline TorchScript loader, then use these thresholds in the agent-side board decoder.

## What comes next

The next stage is to export and validate an inline TorchScript loader using the course-provided `generate_torch_loader_snippet(...)` helper. Then embed that loader in the agent, batch-classify all board cells, enforce board constraints, and validate reconstructed boards and end-to-end episodes.
