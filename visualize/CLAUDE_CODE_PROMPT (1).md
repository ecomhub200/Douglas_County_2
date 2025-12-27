# CRASH LENS - Visualization Module Implementation

## Project Context

You are working on CRASH LENS, a traffic safety analysis tool for Henrico County, Virginia. This tool analyzes crash data, recommends countermeasures using CMF (Crash Modification Factor) data, and generates professional reports.

**Your Task:** Create a new `visualize/` folder and implement a simulation visualization feature that integrates CARLA driving simulator with the existing CRASH LENS application. This feature allows users to see before/after simulations of recommended countermeasures (e.g., signal installation, roundabouts).

---

## Folder Structure to Create

```
visualize/
├── README.md                     # Documentation for this module
├── requirements.txt              # Python dependencies for simulation
│
├── frontend/                     # React components for CRASH LENS UI
│   ├── VisualizeImpactButton.jsx    # Button component for countermeasure cards
│   ├── SimulationConfigModal.jsx    # Configuration modal (time, weather, duration)
│   ├── SimulationProgress.jsx       # Loading/progress indicator
│   ├── SimulationViewer.jsx         # Main split-screen video viewer
│   └── index.js                     # Export all components
│
├── backend/                      # FastAPI backend for simulation processing
│   ├── __init__.py
│   ├── main.py                      # FastAPI app entry point
│   ├── routes/
│   │   ├── __init__.py
│   │   └── simulation.py            # /simulate endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── scenario_generator.py    # Creates OpenDRIVE/OpenSCENARIO files
│   │   ├── sumo_controller.py       # SUMO network generation and control
│   │   ├── carla_controller.py      # CARLA simulation and recording
│   │   └── video_processor.py       # Frame capture and video encoding
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py               # Pydantic models for API
│   └── config.py                    # Configuration settings
│
├── scenarios/                    # Intersection templates and scenarios
│   ├── templates/                   # Reusable intersection templates
│   │   ├── 4leg_stopcontrolled/
│   │   ├── 4leg_signalized/
│   │   └── 3leg_unsignalized/
│   └── countermeasures/             # Countermeasure scenario definitions
│       ├── signal_installation.json
│       ├── roundabout_conversion.json
│       └── rrfb_installation.json
│
├── scripts/                      # Utility scripts
│   ├── setup_carla.sh               # CARLA installation helper
│   ├── test_connection.py           # Test SUMO-CARLA bridge
│   └── generate_intersection.py     # CLI tool to create new intersections
│
└── tests/                        # Unit and integration tests
    ├── __init__.py
    ├── test_scenario_generator.py
    ├── test_simulation_api.py
    └── test_video_processor.py
```

---

## Implementation Steps

### Step 1: Create Folder Structure and README

Create the `visualize/` folder with all subdirectories. Start with a comprehensive README.md that explains:
- Purpose of this module
- Prerequisites (CARLA, SUMO, GPU requirements)
- Installation instructions
- How to run locally
- API documentation overview

### Step 2: Backend - Pydantic Models (backend/models/schemas.py)

Define data models for the API:

```python
from pydantic import BaseModel
from enum import Enum
from typing import Optional

class TimeOfDay(str, Enum):
    AM_PEAK = "am-peak"
    PM_PEAK = "pm-peak"
    OFF_PEAK = "off-peak"

class WeatherCondition(str, Enum):
    DRY = "dry"
    WET = "wet"
    NIGHT = "night"

class Countermeasure(str, Enum):
    SIGNAL = "signal"
    ROUNDABOUT = "roundabout"
    RRFB = "rrfb"
    LEFT_TURN_PHASE = "left-turn-phase"

class SimulationRequest(BaseModel):
    intersection_id: str
    countermeasure: Countermeasure
    time_of_day: TimeOfDay = TimeOfDay.PM_PEAK
    weather: WeatherCondition = WeatherCondition.DRY
    duration: int = 60  # seconds

class SimulationStatus(str, Enum):
    QUEUED = "queued"
    LOADING_GEOMETRY = "loading_geometry"
    CONFIGURING_TRAFFIC = "configuring_traffic"
    GENERATING_NETWORK = "generating_network"
    RENDERING = "rendering"
    ENCODING = "encoding"
    COMPLETE = "complete"
    FAILED = "failed"

class SimulationResponse(BaseModel):
    job_id: str
    status: SimulationStatus
    progress: int = 0
    message: Optional[str] = None
    before_video_url: Optional[str] = None
    after_video_url: Optional[str] = None
    metrics: Optional[dict] = None
```

### Step 3: Backend - FastAPI Routes (backend/routes/simulation.py)

Implement the simulation API endpoints:

```python
from fastapi import APIRouter, BackgroundTasks, HTTPException
from uuid import uuid4
import asyncio

router = APIRouter(prefix="/api/simulation", tags=["simulation"])

# In-memory job storage (replace with Redis in production)
jobs = {}

@router.post("/start")
async def start_simulation(request: SimulationRequest, background_tasks: BackgroundTasks):
    """Start a new simulation job"""
    job_id = str(uuid4())
    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "request": request.dict()
    }
    background_tasks.add_task(run_simulation_pipeline, job_id, request)
    return {"job_id": job_id, "status": "queued"}

@router.get("/status/{job_id}")
async def get_simulation_status(job_id: str):
    """Check status of a simulation job"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@router.delete("/cancel/{job_id}")
async def cancel_simulation(job_id: str):
    """Cancel a running simulation"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    # Implement cancellation logic
    jobs[job_id]["status"] = "cancelled"
    return {"message": "Simulation cancelled"}

async def run_simulation_pipeline(job_id: str, request: SimulationRequest):
    """Background task that runs the full simulation pipeline"""
    try:
        # Step 1: Load intersection geometry
        jobs[job_id]["status"] = "loading_geometry"
        jobs[job_id]["progress"] = 10
        # await load_intersection(request.intersection_id)
        
        # Step 2: Configure traffic volumes
        jobs[job_id]["status"] = "configuring_traffic"
        jobs[job_id]["progress"] = 30
        # await configure_traffic(request)
        
        # Step 3: Generate SUMO network
        jobs[job_id]["status"] = "generating_network"
        jobs[job_id]["progress"] = 50
        # await generate_sumo_network(request)
        
        # Step 4: Render in CARLA
        jobs[job_id]["status"] = "rendering"
        jobs[job_id]["progress"] = 70
        # before_frames, after_frames = await render_simulation(request)
        
        # Step 5: Encode videos
        jobs[job_id]["status"] = "encoding"
        jobs[job_id]["progress"] = 90
        # before_url, after_url = await encode_videos(before_frames, after_frames)
        
        # Complete
        jobs[job_id]["status"] = "complete"
        jobs[job_id]["progress"] = 100
        # jobs[job_id]["before_video_url"] = before_url
        # jobs[job_id]["after_video_url"] = after_url
        
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["message"] = str(e)
```

### Step 4: Backend - CARLA Controller (backend/services/carla_controller.py)

Create the CARLA simulation controller:

```python
import carla
import cv2
import numpy as np
from pathlib import Path

class CarlaController:
    def __init__(self, host='localhost', port=2000):
        self.client = None
        self.world = None
        self.host = host
        self.port = port
        
    async def connect(self):
        """Connect to CARLA server"""
        self.client = carla.Client(self.host, self.port)
        self.client.set_timeout(30.0)
        self.world = self.client.get_world()
        
    async def load_map(self, xodr_path: str):
        """Load custom OpenDRIVE map"""
        with open(xodr_path, 'r') as f:
            xodr_content = f.read()
        self.world = self.client.generate_opendrive_world(xodr_content)
        
    async def setup_weather(self, condition: str):
        """Configure weather conditions"""
        weather = carla.WeatherParameters()
        if condition == "wet":
            weather.precipitation = 80.0
            weather.precipitation_deposits = 60.0
        elif condition == "night":
            weather.sun_altitude_angle = -30.0
        self.world.set_weather(weather)
        
    async def setup_camera(self, location, rotation):
        """Attach spectator camera for recording"""
        blueprint = self.world.get_blueprint_library().find('sensor.camera.rgb')
        blueprint.set_attribute('image_size_x', '1920')
        blueprint.set_attribute('image_size_y', '1080')
        blueprint.set_attribute('fov', '90')
        
        transform = carla.Transform(
            carla.Location(**location),
            carla.Rotation(**rotation)
        )
        camera = self.world.spawn_actor(blueprint, transform)
        return camera
        
    async def record_simulation(self, duration_seconds: int, output_dir: Path):
        """Record simulation frames"""
        frames = []
        fps = 30
        
        # Set synchronous mode
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1.0 / fps
        self.world.apply_settings(settings)
        
        for _ in range(duration_seconds * fps):
            self.world.tick()
            # Capture frame from camera
            # frames.append(frame)
            
        return frames
        
    async def encode_video(self, frames: list, output_path: Path):
        """Encode frames to MP4 video"""
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_path), fourcc, 30, (1920, 1080))
        
        for frame in frames:
            out.write(frame)
        out.release()
        
        return output_path
        
    async def cleanup(self):
        """Clean up actors and reset world"""
        actors = self.world.get_actors()
        for actor in actors:
            if actor.type_id.startswith('vehicle') or actor.type_id.startswith('sensor'):
                actor.destroy()
```

### Step 5: Frontend - React Components

#### VisualizeImpactButton.jsx
```jsx
import React from 'react';
import { Eye } from 'lucide-react';

export function VisualizeImpactButton({ onClick, disabled = false }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg transition-colors"
    >
      <Eye className="w-4 h-4" />
      Visualize Impact
    </button>
  );
}
```

#### SimulationConfigModal.jsx
```jsx
import React, { useState } from 'react';
import { X, ChevronRight } from 'lucide-react';

export function SimulationConfigModal({ 
  isOpen, 
  onClose, 
  onStart, 
  intersection, 
  countermeasure 
}) {
  const [config, setConfig] = useState({
    timeOfDay: 'pm-peak',
    weather: 'dry',
    duration: 60
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div>
            <h3 className="text-lg font-semibold">Configure Simulation</h3>
            <p className="text-sm text-gray-500">{countermeasure} at {intersection}</p>
          </div>
          <button onClick={onClose}>
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Config Options */}
        <div className="p-6 space-y-6">
          {/* Time of Day */}
          <div>
            <label className="block text-sm font-medium mb-2">Time of Day</label>
            <div className="grid grid-cols-3 gap-2">
              {['am-peak', 'pm-peak', 'off-peak'].map(time => (
                <button
                  key={time}
                  onClick={() => setConfig({ ...config, timeOfDay: time })}
                  className={`p-3 rounded-lg border-2 ${
                    config.timeOfDay === time ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                  }`}
                >
                  {time.replace('-', ' ').toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Weather */}
          <div>
            <label className="block text-sm font-medium mb-2">Weather</label>
            <div className="grid grid-cols-3 gap-2">
              {['dry', 'wet', 'night'].map(weather => (
                <button
                  key={weather}
                  onClick={() => setConfig({ ...config, weather })}
                  className={`p-3 rounded-lg border-2 ${
                    config.weather === weather ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                  }`}
                >
                  {weather.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Duration */}
          <div>
            <label className="block text-sm font-medium mb-2">Duration</label>
            <select
              value={config.duration}
              onChange={(e) => setConfig({ ...config, duration: parseInt(e.target.value) })}
              className="w-full p-3 border rounded-lg"
            >
              <option value={30}>30 seconds</option>
              <option value={60}>60 seconds</option>
              <option value={120}>2 minutes</option>
            </select>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 p-4 border-t">
          <button onClick={onClose} className="px-4 py-2 text-gray-600">
            Cancel
          </button>
          <button
            onClick={() => onStart(config)}
            className="flex items-center gap-2 bg-blue-600 text-white px-6 py-2 rounded-lg"
          >
            Generate Simulation
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
```

#### SimulationViewer.jsx
```jsx
import React, { useState } from 'react';
import { Play, Pause, RotateCcw, Download, X, Camera, Video, FileText } from 'lucide-react';

export function SimulationViewer({ 
  isOpen, 
  onClose, 
  beforeVideoUrl, 
  afterVideoUrl,
  metrics,
  onAddToReport 
}) {
  const [viewMode, setViewMode] = useState('split');
  const [isPlaying, setIsPlaying] = useState(false);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/90 flex flex-col z-50">
      {/* Header */}
      <div className="bg-gray-900 px-6 py-4 flex justify-between">
        <div>
          <h3 className="text-white font-semibold">Simulation Results</h3>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-white">
          <X className="w-6 h-6" />
        </button>
      </div>

      {/* View Mode Toggle */}
      <div className="bg-gray-800 px-6 py-2 flex gap-4">
        {['split', 'before', 'after'].map(mode => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            className={`px-3 py-1 rounded ${
              viewMode === mode ? 'bg-blue-600 text-white' : 'text-gray-400'
            }`}
          >
            {mode.charAt(0).toUpperCase() + mode.slice(1)}
          </button>
        ))}
      </div>

      {/* Video Display */}
      <div className="flex-1 flex">
        {(viewMode === 'split' || viewMode === 'before') && (
          <div className={viewMode === 'split' ? 'w-1/2' : 'w-full'}>
            <video src={beforeVideoUrl} controls className="w-full h-full object-cover" />
          </div>
        )}
        {(viewMode === 'split' || viewMode === 'after') && (
          <div className={viewMode === 'split' ? 'w-1/2' : 'w-full'}>
            <video src={afterVideoUrl} controls className="w-full h-full object-cover" />
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="bg-gray-900 px-6 py-4 flex justify-between">
        <div className="flex gap-2">
          <button className="p-2 bg-gray-700 rounded-full">
            {isPlaying ? <Pause /> : <Play />}
          </button>
        </div>
        <div className="flex gap-2">
          <button className="flex items-center gap-2 px-3 py-2 bg-gray-700 rounded-lg text-white">
            <Video className="w-4 h-4" />
            Export Video
          </button>
          <button 
            onClick={onAddToReport}
            className="flex items-center gap-2 px-3 py-2 bg-green-600 rounded-lg text-white"
          >
            <FileText className="w-4 h-4" />
            Add to Report
          </button>
        </div>
      </div>

      {/* Metrics Summary */}
      {metrics && (
        <div className="bg-gray-800 px-6 py-3 flex gap-8">
          <div>
            <span className="text-gray-400">Crash Reduction:</span>
            <span className="text-green-400 font-bold ml-2">{metrics.crashReduction}%</span>
          </div>
          <div>
            <span className="text-gray-400">Annual Savings:</span>
            <span className="text-green-400 font-bold ml-2">${metrics.annualSavings.toLocaleString()}</span>
          </div>
        </div>
      )}
    </div>
  );
}
```

### Step 6: Integration Hook for Existing CRASH LENS

Create a custom React hook to manage simulation state:

```jsx
// frontend/hooks/useSimulation.js

import { useState, useCallback } from 'react';

export function useSimulation() {
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [isViewerOpen, setIsViewerOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const startSimulation = useCallback(async (intersectionId, countermeasure, config) => {
    setIsLoading(true);
    setError(null);
    
    try {
      // Start simulation job
      const response = await fetch('/api/simulation/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          intersection_id: intersectionId,
          countermeasure,
          ...config
        })
      });
      
      const { job_id } = await response.json();
      
      // Poll for status
      const pollInterval = setInterval(async () => {
        const statusRes = await fetch(`/api/simulation/status/${job_id}`);
        const status = await statusRes.json();
        
        setProgress(status.progress);
        
        if (status.status === 'complete') {
          clearInterval(pollInterval);
          setResults({
            beforeVideoUrl: status.before_video_url,
            afterVideoUrl: status.after_video_url,
            metrics: status.metrics
          });
          setIsLoading(false);
          setIsViewerOpen(true);
        } else if (status.status === 'failed') {
          clearInterval(pollInterval);
          setError(status.message);
          setIsLoading(false);
        }
      }, 1000);
      
    } catch (err) {
      setError(err.message);
      setIsLoading(false);
    }
  }, []);

  return {
    isConfigOpen,
    setIsConfigOpen,
    isViewerOpen,
    setIsViewerOpen,
    isLoading,
    progress,
    results,
    error,
    startSimulation
  };
}
```

---

## Configuration Files

### requirements.txt
```
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0
carla>=0.9.15
opencv-python>=4.8.0
numpy>=1.24.0
redis>=4.6.0
python-multipart>=0.0.6
aiofiles>=23.1.0
```

### backend/config.py
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # CARLA Settings
    carla_host: str = "localhost"
    carla_port: int = 2000
    
    # SUMO Settings
    sumo_binary: str = "sumo"
    
    # Storage
    video_output_dir: str = "./outputs/videos"
    scenario_dir: str = "./scenarios"
    
    # Redis (for job queue)
    redis_url: str = "redis://localhost:6379"
    
    class Config:
        env_file = ".env"

settings = Settings()
```

---

## Testing Your Implementation

1. **Test CARLA Connection:**
```bash
cd visualize
python scripts/test_connection.py
```

2. **Test API Locally:**
```bash
cd visualize/backend
uvicorn main:app --reload --port 8001
# Then visit http://localhost:8001/docs for Swagger UI
```

3. **Test Frontend Components:**
```bash
# From CRASH LENS root
npm run storybook  # If using Storybook
# Or integrate into existing dev server
```

---

## Notes for Claude Code

- Follow existing CRASH LENS code style and conventions
- Use TypeScript if the existing frontend uses TypeScript
- Add proper error handling and loading states
- Include comments explaining CARLA/SUMO integration points
- Create placeholder functions where actual CARLA integration will happen
- Make components modular so they can be easily integrated into existing countermeasure recommendation UI
- Use environment variables for all configurable values
- Add JSDoc/docstrings for all functions and classes

---

## Questions to Ask User

Before starting implementation, clarify:
1. Is the existing CRASH LENS frontend using TypeScript or JavaScript?
2. What state management is used (Redux, Zustand, Context)?
3. What CSS framework is used (Tailwind, styled-components, CSS modules)?
4. Is there an existing API structure to follow?
5. Where should the backend be deployed (same server, separate service)?
