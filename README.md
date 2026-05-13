# Attractor-Basin Cognition

Attractor-Basin Cognition (ABC) is a standalone Python library for modeling cognitive signals as attractor-basin dynamics.

Tagline: all cognition is attractor basins when done right.

ABC is not a host application. It does not import or depend on agent servers, graph databases, webhooks, or any project-specific cognitive model. Hosts translate their own objects into ABC's neutral signal protocols.

## What It Provides

- Hopfield-backed basin creation, recall, strengthening, and stability checks.
- Oscillatory basin-field dynamics for basin influence, resonance, coupling, and persistence profiles.
- A host-adapter boundary for cognitive systems that need to route signals without coupling this library to their object model.
- Neutral signal protocols for a ladder from impulse-scale activation to packet-like signals, concept fields, and basin graphs.

## Signal Ladder

ABC keeps the public API neutral:

- `BasinImpulse`: a minimal activation plus optional dominant basin.
- `PacketLike`: a packet-scale signal with content, precision, coherence, and metadata.
- `ConceptFieldLike`: a field-scale signal with concepts, field energy, and a dominant basin.
- `BasinGraphLike`: a graph-scale signal with constituent basins, cohesion, and stability.

Application-specific objects belong in host adapters, not inside this package.

## Install

```bash
pip install attractor-basin-cognition
```

## Quick Start

```python
from abcognition import CoreAttractorService

service = CoreAttractorService(n_units=128)

await service.create_basin(
    "procedural-basin",
    "stepwise task execution and tool use",
)

await service.create_basin(
    "experiential-basin",
    "episodic recall and lived context",
)

result = await service.find_nearest_basin("remember what happened last session")
```

Field dynamics:

```python
from abcognition.field import BasinFieldEngine

field = BasinFieldEngine(["experiential-basin", "procedural-basin"])
state = await field.step({
    "experiential-basin": 0.8,
    "procedural-basin": 0.2,
})

print(state.influence)
print(state.resonance)
```

## Host-Adapter Boundary

ABC owns basin math and signal contracts. Your host owns identity, persistence policy, memory graphs, agent lifecycle, domain schemas, and product-specific names.

Correct integration shape:

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class MyHostSignal:
    activation_level: float
    dominant_basin: Optional[str]
```

Then pass host data through ABC protocols or services without ABC importing the host.

## Current Status

This is an alpha extraction. The initial package includes the reusable attractor service, basin state model, field engine, field state model, and neutral protocols. Higher-level mental model helpers should be added only when they remain host-neutral.
