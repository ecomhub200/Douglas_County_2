# Visualize Impact Module - Implementation Recommendations

## Overview

This document outlines the recommended approach for implementing the CARLA/SUMO simulation visualization feature for CRASH LENS.

---

## Recommended Folder Structure

```
visualize/
├── README.md                         # Module documentation
├── IMPLEMENTATION_RECOMMENDATIONS.md # This file
├── requirements.txt                  # Python dependencies
│
├── frontend/                         # UI Components
│   ├── components/
│   │   ├── VisualizeImpactButton.jsx
│   │   ├── SimulationConfigModal.jsx
│   │   ├── SimulationProgress.jsx
│   │   └── SimulationViewer.jsx
│   ├── hooks/
│   │   └── useSimulation.js
│   └── index.js
│
├── backend/                          # FastAPI Backend
│   ├── main.py                       # Entry point
│   ├── config.py                     # Settings
│   ├── routes/
│   │   └── simulation.py             # API endpoints
│   ├── services/
│   │   ├── scenario_generator.py     # OpenDRIVE/OpenSCENARIO
│   │   ├── sumo_controller.py        # SUMO integration
│   │   ├── carla_controller.py       # CARLA integration
│   │   └── video_processor.py        # Video encoding
│   └── models/
│       └── schemas.py                # Pydantic models
│
├── scenarios/                        # Intersection templates
│   ├── templates/
│   │   ├── 4leg_stopcontrolled/
│   │   ├── 4leg_signalized/
│   │   ├── 3leg_unsignalized/
│   │   └── roundabout/
│   └── countermeasures/
│       ├── signal_installation.json
│       ├── roundabout_conversion.json
│       └── rrfb_installation.json
│
├── scripts/                          # Utilities
│   ├── setup_carla.sh
│   ├── test_connection.py
│   └── generate_intersection.py
│
└── tests/                            # Test suite
    ├── test_scenario_generator.py
    ├── test_simulation_api.py
    └── test_video_processor.py
```

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
**Goal:** Set up infrastructure and basic API

1. Create folder structure
2. Set up FastAPI backend scaffold
3. Define Pydantic models for simulation requests/responses
4. Create basic API endpoints (start, status, cancel)
5. Implement job queue with Redis or in-memory storage

**Deliverables:**
- Working API that accepts simulation requests
- Job status tracking system
- Docker Compose for local development

---

### Phase 2: SUMO Integration (Weeks 3-4)
**Goal:** Generate traffic networks and simulate flows

1. Create intersection template system (OpenDRIVE format)
2. Build SUMO network generator from templates
3. Implement traffic volume configuration
4. Add countermeasure scenario definitions
5. Run SUMO simulations and collect metrics

**Deliverables:**
- Parameterized intersection templates
- SUMO simulation runner
- Conflict/delay metrics extraction

---

### Phase 3: CARLA Visualization (Weeks 5-7)
**Goal:** 3D rendering of before/after scenarios

1. Establish CARLA connection and map loading
2. Implement SUMO-CARLA co-simulation bridge
3. Set up camera positioning and recording
4. Configure weather/lighting conditions
5. Capture and encode video output

**Deliverables:**
- Before/after video generation
- Weather condition support
- Synchronized playback videos

---

### Phase 4: Frontend Integration (Weeks 8-9)
**Goal:** Integrate with existing CRASH LENS UI

1. Create React components from mockup
2. Implement simulation state hook
3. Add "Visualize Impact" button to CMF tab
4. Build configuration modal
5. Create split-screen video viewer

**Deliverables:**
- Complete UI flow
- Integration with countermeasure cards
- Video playback controls

---

### Phase 5: Polish & Optimization (Weeks 10-12)
**Goal:** Production readiness

1. Video caching system
2. Pre-generate common scenarios
3. Add export to report functionality
4. Performance optimization
5. Comprehensive testing

**Deliverables:**
- Production-ready module
- Documentation
- Test coverage

---

## Technology Recommendations

### Backend Stack
| Component | Recommendation | Alternative |
|-----------|---------------|-------------|
| API Framework | FastAPI | Flask |
| Job Queue | Redis + Celery | In-memory (dev only) |
| Traffic Sim | SUMO | Aimsun, VISSIM |
| 3D Rendering | CARLA | Pre-rendered animations |
| Video Encoding | FFmpeg + OpenCV | MoviePy |

### Frontend Stack
| Component | Recommendation | Rationale |
|-----------|---------------|-----------|
| Components | React (match existing) | Integration |
| State | useSimulation hook | Simplicity |
| Video Player | Custom with HTML5 | Control |
| Styling | Tailwind CSS | Match mockup |

---

## Key Technical Considerations

### 1. Server Requirements
- **GPU Required:** CARLA needs NVIDIA GPU (GTX 1070+ recommended)
- **Memory:** 16GB+ RAM for concurrent simulations
- **Storage:** ~500MB per simulation video

### 2. Performance Optimization
- **Caching:** Cache completed simulations by intersection + countermeasure + config hash
- **Async Processing:** Use background tasks, don't block API
- **Batch Processing:** Pre-generate popular scenarios during off-hours

### 3. Fallback Options
If CARLA is not available or too resource-intensive:

| Option | Pros | Cons |
|--------|------|------|
| 2D SUMO visualization | Lightweight, fast | Less impactful |
| Pre-rendered videos | No GPU needed | Limited customization |
| Animated diagrams | Very lightweight | Less realistic |

### 4. Integration Points

**With Existing CRASH LENS:**
- Add button to CMF countermeasure cards
- Use existing `cmfState.selectedLocation` for intersection ID
- Match existing UI patterns and styling
- Add to report generation system

---

## API Design

### Start Simulation
```
POST /api/simulation/start
{
  "intersection_id": "INT-2847",
  "countermeasure": "signal",
  "time_of_day": "pm-peak",
  "weather": "dry",
  "duration": 60
}
Response: { "job_id": "uuid", "status": "queued" }
```

### Check Status
```
GET /api/simulation/status/{job_id}
Response: {
  "status": "rendering",
  "progress": 70,
  "message": "Generating CARLA visualization..."
}
```

### Get Results
```
GET /api/simulation/results/{job_id}
Response: {
  "before_video_url": "/videos/abc123-before.mp4",
  "after_video_url": "/videos/abc123-after.mp4",
  "metrics": {
    "before_conflicts": 4.6,
    "after_conflicts": 0.8,
    "conflict_reduction": 83
  }
}
```

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CARLA complexity | High | High | Start with SUMO-only, add CARLA later |
| GPU unavailable | Medium | High | Offer 2D fallback mode |
| Long generation time | High | Medium | Progress indicators, caching |
| Integration issues | Medium | Medium | Modular design, clear API |

---

## Next Steps

1. **Immediate:** Create README.md with setup instructions
2. **Week 1:** Set up backend folder structure and FastAPI scaffold
3. **Week 2:** Implement basic API with mock responses
4. **Week 3:** Begin SUMO integration with simple template

---

## Questions to Resolve

Before starting implementation:

1. **Hosting:** Where will the backend be deployed? (Same server, separate GPU instance, cloud service?)
2. **Budget:** GPU server costs for CARLA (~$200-500/month for cloud)
3. **Scope:** Start with 3-4 countermeasure types or full CMF catalog?
4. **Priority:** CARLA 3D essential, or 2D SUMO acceptable for MVP?

---

## Resources

- [CARLA Documentation](https://carla.readthedocs.io/)
- [SUMO Documentation](https://sumo.dlr.de/docs/)
- [SUMO-CARLA Co-simulation](https://carla.readthedocs.io/en/latest/adv_sumo/)
- [OpenDRIVE Specification](https://www.asam.net/standards/detail/opendrive/)
