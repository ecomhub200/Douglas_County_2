import React, { useState } from 'react';
import { Play, Pause, RotateCcw, Download, X, Camera, Video, FileText, ChevronRight, AlertTriangle, CheckCircle, Settings, Eye } from 'lucide-react';

export default function VisualizeImpactMockup() {
  const [currentView, setCurrentView] = useState('recommendations'); // recommendations, config, simulating, results
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [simulationProgress, setSimulationProgress] = useState(0);
  const [viewMode, setViewMode] = useState('split'); // split, before, after
  const [selectedConfig, setSelectedConfig] = useState({
    timeOfDay: 'pm-peak',
    weather: 'dry',
    duration: '60'
  });

  // Simulate the loading process
  const startSimulation = () => {
    setCurrentView('simulating');
    setSimulationProgress(0);
    const interval = setInterval(() => {
      setSimulationProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setTimeout(() => setCurrentView('results'), 500);
          return 100;
        }
        return prev + Math.random() * 15;
      });
    }, 400);
  };

  const resetDemo = () => {
    setCurrentView('recommendations');
    setProgress(0);
    setSimulationProgress(0);
    setIsPlaying(false);
  };

  // Countermeasure Recommendations View
  const RecommendationsView = () => (
    <div className="bg-white rounded-xl shadow-lg p-6 max-w-4xl mx-auto">
      <div className="border-b pb-4 mb-6">
        <h2 className="text-xl font-bold text-gray-800">Countermeasure Recommendations</h2>
        <p className="text-gray-500 text-sm mt-1">Intersection: Broad St & Main St (ID: INT-2847)</p>
      </div>

      {/* Crash Summary */}
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-2">
          <AlertTriangle className="w-5 h-5 text-red-600" />
          <span className="font-semibold text-red-800">5-Year Crash Summary</span>
        </div>
        <div className="grid grid-cols-4 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-red-700">23</div>
            <div className="text-xs text-gray-600">Total Crashes</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-red-700">2</div>
            <div className="text-xs text-gray-600">Fatal/Serious</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-red-700">68%</div>
            <div className="text-xs text-gray-600">Angle Crashes</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-red-700">$2.4M</div>
            <div className="text-xs text-gray-600">Est. Crash Cost</div>
          </div>
        </div>
      </div>

      {/* Recommendations */}
      <div className="space-y-4">
        {/* Primary Recommendation */}
        <div className="border-2 border-blue-200 bg-blue-50 rounded-lg p-4">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="bg-blue-600 text-white text-xs px-2 py-1 rounded">RECOMMENDED</span>
                <span className="text-sm text-gray-500">CMF: 0.56</span>
              </div>
              <h3 className="text-lg font-semibold text-gray-800 mt-2">Install Traffic Signal</h3>
              <p className="text-sm text-gray-600 mt-1">
                Based on crash patterns and volume data, signal installation is projected to reduce crashes by 44%.
              </p>
              <div className="flex items-center gap-6 mt-3 text-sm">
                <div>
                  <span className="text-gray-500">Est. Cost:</span>
                  <span className="font-semibold text-gray-800 ml-1">$175,000</span>
                </div>
                <div>
                  <span className="text-gray-500">B/C Ratio:</span>
                  <span className="font-semibold text-green-600 ml-1">3.2</span>
                </div>
                <div>
                  <span className="text-gray-500">Crashes Prevented:</span>
                  <span className="font-semibold text-green-600 ml-1">~10 over 5 years</span>
                </div>
              </div>
            </div>
            <button
              onClick={() => setCurrentView('config')}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
            >
              <Eye className="w-4 h-4" />
              Visualize Impact
            </button>
          </div>
        </div>

        {/* Secondary Recommendation */}
        <div className="border border-gray-200 rounded-lg p-4">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="bg-gray-400 text-white text-xs px-2 py-1 rounded">ALTERNATIVE</span>
                <span className="text-sm text-gray-500">CMF: 0.71</span>
              </div>
              <h3 className="text-lg font-semibold text-gray-800 mt-2">Roundabout Conversion</h3>
              <p className="text-sm text-gray-600 mt-1">
                Single-lane roundabout would reduce crashes by 29% with additional safety co-benefits.
              </p>
              <div className="flex items-center gap-6 mt-3 text-sm">
                <div>
                  <span className="text-gray-500">Est. Cost:</span>
                  <span className="font-semibold text-gray-800 ml-1">$850,000</span>
                </div>
                <div>
                  <span className="text-gray-500">B/C Ratio:</span>
                  <span className="font-semibold text-yellow-600 ml-1">1.4</span>
                </div>
              </div>
            </div>
            <button className="flex items-center gap-2 bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2 rounded-lg transition-colors">
              <Eye className="w-4 h-4" />
              Visualize Impact
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  // Configuration Modal
  const ConfigModal = () => (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full">
        <div className="flex items-center justify-between p-4 border-b">
          <div>
            <h3 className="text-lg font-semibold text-gray-800">Configure Simulation</h3>
            <p className="text-sm text-gray-500">Install Traffic Signal at Broad St & Main St</p>
          </div>
          <button onClick={resetDemo} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Time of Day */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Time of Day</label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: 'am-peak', label: 'AM Peak', desc: '7-9 AM' },
                { id: 'pm-peak', label: 'PM Peak', desc: '4-6 PM' },
                { id: 'off-peak', label: 'Off-Peak', desc: 'Midday' }
              ].map(option => (
                <button
                  key={option.id}
                  onClick={() => setSelectedConfig({ ...selectedConfig, timeOfDay: option.id })}
                  className={`p-3 rounded-lg border-2 text-left transition-all ${
                    selectedConfig.timeOfDay === option.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="font-medium text-gray-800">{option.label}</div>
                  <div className="text-xs text-gray-500">{option.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Weather Conditions */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Weather Conditions</label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: 'dry', label: 'Dry', icon: '☀️' },
                { id: 'wet', label: 'Wet', icon: '🌧️' },
                { id: 'night', label: 'Night', icon: '🌙' }
              ].map(option => (
                <button
                  key={option.id}
                  onClick={() => setSelectedConfig({ ...selectedConfig, weather: option.id })}
                  className={`p-3 rounded-lg border-2 text-center transition-all ${
                    selectedConfig.weather === option.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="text-2xl mb-1">{option.icon}</div>
                  <div className="font-medium text-gray-800">{option.label}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Simulation Duration */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Simulation Duration</label>
            <select
              value={selectedConfig.duration}
              onChange={(e) => setSelectedConfig({ ...selectedConfig, duration: e.target.value })}
              className="w-full p-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="30">30 seconds (Quick Preview)</option>
              <option value="60">60 seconds (Standard)</option>
              <option value="120">2 minutes (Detailed)</option>
            </select>
          </div>

          {/* Info Box */}
          <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-600">
            <div className="flex items-start gap-2">
              <Settings className="w-4 h-4 mt-0.5 text-gray-400" />
              <div>
                <p className="font-medium text-gray-700">What you'll see:</p>
                <ul className="mt-1 space-y-1 text-gray-500">
                  <li>• Side-by-side comparison of current vs. with signal</li>
                  <li>• Traffic flow visualization with conflict highlighting</li>
                  <li>• Projected safety metrics overlay</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 p-4 border-t bg-gray-50 rounded-b-xl">
          <button
            onClick={resetDemo}
            className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={startSimulation}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg transition-colors"
          >
            Generate Simulation
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );

  // Simulating View
  const SimulatingView = () => (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-8 text-center">
        <div className="w-16 h-16 mx-auto mb-6 relative">
          <div className="absolute inset-0 border-4 border-blue-200 rounded-full"></div>
          <div
            className="absolute inset-0 border-4 border-blue-600 rounded-full border-t-transparent animate-spin"
          ></div>
        </div>
        <h3 className="text-xl font-semibold text-gray-800 mb-2">Generating Simulation</h3>
        <p className="text-gray-500 mb-6">Building scenario and rendering visualization...</p>
        
        <div className="space-y-3 text-left mb-6">
          {[
            { label: 'Loading intersection geometry', done: simulationProgress > 20 },
            { label: 'Configuring traffic volumes', done: simulationProgress > 40 },
            { label: 'Generating SUMO network', done: simulationProgress > 60 },
            { label: 'Rendering CARLA visualization', done: simulationProgress > 80 },
            { label: 'Finalizing output', done: simulationProgress >= 100 }
          ].map((step, i) => (
            <div key={i} className="flex items-center gap-3">
              {step.done ? (
                <CheckCircle className="w-5 h-5 text-green-500" />
              ) : (
                <div className="w-5 h-5 border-2 border-gray-300 rounded-full" />
              )}
              <span className={step.done ? 'text-gray-800' : 'text-gray-400'}>{step.label}</span>
            </div>
          ))}
        </div>

        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
            style={{ width: `${Math.min(simulationProgress, 100)}%` }}
          />
        </div>
        <p className="text-sm text-gray-500 mt-2">{Math.round(Math.min(simulationProgress, 100))}% complete</p>
      </div>
    </div>
  );

  // Results View
  const ResultsView = () => (
    <div className="fixed inset-0 bg-black/90 flex flex-col z-50">
      {/* Header */}
      <div className="bg-gray-900 px-6 py-4 flex items-center justify-between">
        <div>
          <h3 className="text-white font-semibold">Simulation: Install Traffic Signal</h3>
          <p className="text-gray-400 text-sm">Broad St & Main St • PM Peak • Dry Conditions</p>
        </div>
        <button onClick={resetDemo} className="text-gray-400 hover:text-white">
          <X className="w-6 h-6" />
        </button>
      </div>

      {/* View Mode Toggle */}
      <div className="bg-gray-800 px-6 py-2 flex items-center gap-4">
        <span className="text-gray-400 text-sm">View:</span>
        <div className="flex gap-1">
          {[
            { id: 'split', label: 'Split View' },
            { id: 'before', label: 'Before Only' },
            { id: 'after', label: 'After Only' }
          ].map(mode => (
            <button
              key={mode.id}
              onClick={() => setViewMode(mode.id)}
              className={`px-3 py-1 rounded text-sm transition-colors ${
                viewMode === mode.id
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {mode.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex">
        {/* Before View */}
        {(viewMode === 'split' || viewMode === 'before') && (
          <div className={`${viewMode === 'split' ? 'w-1/2' : 'w-full'} relative`}>
            <div className="absolute top-4 left-4 bg-red-600 text-white px-3 py-1 rounded-full text-sm font-medium z-10">
              BEFORE (Current)
            </div>
            <div className="w-full h-full bg-gradient-to-br from-gray-700 to-gray-800 flex items-center justify-center">
              {/* Simulated intersection view - Before */}
              <div className="relative w-80 h-80">
                {/* Roads */}
                <div className="absolute top-1/2 left-0 right-0 h-16 bg-gray-600 -translate-y-1/2"></div>
                <div className="absolute left-1/2 top-0 bottom-0 w-16 bg-gray-600 -translate-x-1/2"></div>
                {/* Center */}
                <div className="absolute top-1/2 left-1/2 w-16 h-16 bg-gray-500 -translate-x-1/2 -translate-y-1/2"></div>
                {/* Stop signs */}
                <div className="absolute top-1/2 left-1/4 w-6 h-6 bg-red-600 -translate-y-1/2 flex items-center justify-center text-white text-xs font-bold">
                  ⬡
                </div>
                <div className="absolute top-1/2 right-1/4 w-6 h-6 bg-red-600 -translate-y-1/2 flex items-center justify-center text-white text-xs font-bold">
                  ⬡
                </div>
                {/* Vehicles with conflict */}
                <div className="absolute top-1/3 left-1/2 w-4 h-6 bg-blue-400 -translate-x-1/2 rounded-sm animate-pulse"></div>
                <div className="absolute top-1/2 left-1/3 w-6 h-4 bg-yellow-400 -translate-y-1/2 rounded-sm animate-pulse"></div>
                {/* Conflict indicator */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
                  <div className="w-12 h-12 border-4 border-red-500 rounded-full animate-ping opacity-50"></div>
                </div>
              </div>
            </div>
            {/* Stats Overlay */}
            <div className="absolute bottom-4 left-4 right-4 bg-black/70 rounded-lg p-3">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-red-400 text-lg font-bold">4.6/hr</div>
                  <div className="text-gray-400 text-xs">Conflicts</div>
                </div>
                <div>
                  <div className="text-yellow-400 text-lg font-bold">23.5s</div>
                  <div className="text-gray-400 text-xs">Avg Delay</div>
                </div>
                <div>
                  <div className="text-red-400 text-lg font-bold">High</div>
                  <div className="text-gray-400 text-xs">Risk Level</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Divider */}
        {viewMode === 'split' && (
          <div className="w-1 bg-white/20"></div>
        )}

        {/* After View */}
        {(viewMode === 'split' || viewMode === 'after') && (
          <div className={`${viewMode === 'split' ? 'w-1/2' : 'w-full'} relative`}>
            <div className="absolute top-4 left-4 bg-green-600 text-white px-3 py-1 rounded-full text-sm font-medium z-10">
              AFTER (With Signal)
            </div>
            <div className="w-full h-full bg-gradient-to-br from-gray-700 to-gray-800 flex items-center justify-center">
              {/* Simulated intersection view - After */}
              <div className="relative w-80 h-80">
                {/* Roads */}
                <div className="absolute top-1/2 left-0 right-0 h-16 bg-gray-600 -translate-y-1/2"></div>
                <div className="absolute left-1/2 top-0 bottom-0 w-16 bg-gray-600 -translate-x-1/2"></div>
                {/* Center */}
                <div className="absolute top-1/2 left-1/2 w-16 h-16 bg-gray-500 -translate-x-1/2 -translate-y-1/2"></div>
                {/* Traffic signals */}
                <div className="absolute top-1/4 left-1/2 -translate-x-1/2 flex flex-col gap-0.5 bg-gray-800 p-1 rounded">
                  <div className="w-3 h-3 bg-gray-600 rounded-full"></div>
                  <div className="w-3 h-3 bg-gray-600 rounded-full"></div>
                  <div className="w-3 h-3 bg-green-500 rounded-full shadow-lg shadow-green-500/50"></div>
                </div>
                <div className="absolute bottom-1/4 left-1/2 -translate-x-1/2 flex flex-col gap-0.5 bg-gray-800 p-1 rounded">
                  <div className="w-3 h-3 bg-red-500 rounded-full shadow-lg shadow-red-500/50"></div>
                  <div className="w-3 h-3 bg-gray-600 rounded-full"></div>
                  <div className="w-3 h-3 bg-gray-600 rounded-full"></div>
                </div>
                {/* Vehicles - orderly */}
                <div className="absolute top-1/4 left-1/2 w-4 h-6 bg-blue-400 -translate-x-1/2 rounded-sm"></div>
                <div className="absolute top-1/2 left-1/4 w-6 h-4 bg-yellow-400 -translate-y-1/2 rounded-sm opacity-50"></div>
              </div>
            </div>
            {/* Stats Overlay */}
            <div className="absolute bottom-4 left-4 right-4 bg-black/70 rounded-lg p-3">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-green-400 text-lg font-bold">0.8/hr</div>
                  <div className="text-gray-400 text-xs">Conflicts</div>
                  <div className="text-green-400 text-xs">↓ 83%</div>
                </div>
                <div>
                  <div className="text-green-400 text-lg font-bold">18.2s</div>
                  <div className="text-gray-400 text-xs">Avg Delay</div>
                  <div className="text-green-400 text-xs">↓ 23%</div>
                </div>
                <div>
                  <div className="text-green-400 text-lg font-bold">Low</div>
                  <div className="text-gray-400 text-xs">Risk Level</div>
                  <div className="text-green-400 text-xs">Improved</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Playback Controls */}
      <div className="bg-gray-900 px-6 py-4">
        <div className="flex items-center gap-4">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="w-10 h-10 flex items-center justify-center bg-blue-600 hover:bg-blue-700 rounded-full text-white transition-colors"
          >
            {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
          </button>
          <button className="w-10 h-10 flex items-center justify-center bg-gray-700 hover:bg-gray-600 rounded-full text-white transition-colors">
            <RotateCcw className="w-4 h-4" />
          </button>
          
          {/* Progress Bar */}
          <div className="flex-1 mx-4">
            <div className="w-full bg-gray-700 rounded-full h-2 cursor-pointer">
              <div className="bg-blue-500 h-2 rounded-full" style={{ width: '35%' }}></div>
            </div>
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>0:21</span>
              <span>1:00</span>
            </div>
          </div>

          {/* Export Options */}
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-2 px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white text-sm transition-colors">
              <Camera className="w-4 h-4" />
              Screenshot
            </button>
            <button className="flex items-center gap-2 px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white text-sm transition-colors">
              <Video className="w-4 h-4" />
              Export Video
            </button>
            <button className="flex items-center gap-2 px-3 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-white text-sm transition-colors">
              <FileText className="w-4 h-4" />
              Add to Report
            </button>
          </div>
        </div>
      </div>

      {/* Summary Panel */}
      <div className="bg-gray-800 px-6 py-3 border-t border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-8">
            <div>
              <span className="text-gray-400 text-sm">Projected Crash Reduction:</span>
              <span className="text-green-400 font-bold ml-2">44% (CMF: 0.56)</span>
            </div>
            <div>
              <span className="text-gray-400 text-sm">Estimated Annual Savings:</span>
              <span className="text-green-400 font-bold ml-2">$480,000</span>
            </div>
            <div>
              <span className="text-gray-400 text-sm">Implementation Cost:</span>
              <span className="text-white font-bold ml-2">$175,000</span>
            </div>
          </div>
          <div className="text-gray-400 text-sm">
            Powered by SUMO + CARLA
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Demo Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800">CRASH LENS</h1>
          <p className="text-gray-500">Simulation Visualization Feature Mockup</p>
          <div className="mt-4 flex justify-center gap-2">
            <span className={`px-3 py-1 rounded-full text-sm ${currentView === 'recommendations' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'}`}>
              1. Recommendations
            </span>
            <span className={`px-3 py-1 rounded-full text-sm ${currentView === 'config' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'}`}>
              2. Configure
            </span>
            <span className={`px-3 py-1 rounded-full text-sm ${currentView === 'simulating' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'}`}>
              3. Generate
            </span>
            <span className={`px-3 py-1 rounded-full text-sm ${currentView === 'results' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'}`}>
              4. Results
            </span>
          </div>
        </div>

        {/* Main Content */}
        <RecommendationsView />

        {/* Modals */}
        {currentView === 'config' && <ConfigModal />}
        {currentView === 'simulating' && <SimulatingView />}
        {currentView === 'results' && <ResultsView />}

        {/* Reset Button */}
        {currentView !== 'recommendations' && currentView !== 'config' && currentView !== 'simulating' && (
          <div className="fixed bottom-8 right-8">
            <button
              onClick={resetDemo}
              className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 text-white px-4 py-2 rounded-lg shadow-lg transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
              Reset Demo
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
