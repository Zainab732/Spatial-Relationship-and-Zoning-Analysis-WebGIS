import React, { useEffect, useState, useCallback } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMapEvents, LayersControl } from 'react-leaflet';
import * as turf from '@turf/turf';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './App.css';

const { BaseLayer } = LayersControl;

function MapEvents({ onMove }) {
    const map = useMapEvents({
        moveend: () => {
            const b = map.getBounds();
            onMove({ min_lon: b.getWest(), min_lat: b.getSouth(), max_lon: b.getEast(), max_lat: b.getNorth() });
        }
    });
    return null;
}

function App() {
    const [layers, setLayers] = useState({
        buildings: { data: null, visible: true, color: '#e74c3c', label: 'Buildings' },
        zoning: { data: null, visible: false, color: '#f1c40f', label: 'Zoning Map' },
        parcels: { data: null, visible: false, color: '#3498db', label: 'Admin Parcels' }
    });
    const [buffer, setBuffer] = useState(null);
    const [stats, setStats] = useState({ compliant: 0, conflict: 0 });

    const fetchAll = useCallback((bbox) => {
        const params = `min_lon=${bbox.min_lon}&min_lat=${bbox.min_lat}&max_lon=${bbox.max_lon}&max_lat=${bbox.max_lat}`;
        
        // Fetch All Layers
        ['buildings', 'zoning', 'parcels'].forEach(key => {
            fetch(`http://127.0.0.1:8000/${key}?${params}`)
                .then(r => r.json())
                .then(data => {
                    console.log(`${key} Loaded:`, data.features?.length || 0); // Log count for debugging
                    setLayers(prev => ({ ...prev, [key]: { ...prev[key], data } }));
                    if (key === 'buildings' && data.features) {
                        const conf = data.features.filter(f => f.properties.status === 'Conflict').length;
                        setStats({ conflict: conf, compliant: data.features.length - conf });
                    }
                });
        });
    }, []);

    useEffect(() => { 
        fetchAll({ min_lon: -122.34, min_lat: 47.60, max_lon: -122.32, max_lat: 47.62 }); 
    }, [fetchAll]);

    // Buffer functionality
    const handleBuildingClick = (feature) => {
        setBuffer(null);
        setTimeout(() => {
            const poly = turf.buffer(feature, 100, { units: 'meters' });
            setBuffer(poly);
        }, 10);
    };

    return (
        <div className="App">
            <div className="sidebar">
                <h2>LZPA GIS</h2>
                <div className="stat-card">
                    <p>🟢 Compliant: {stats.compliant}</p>
                    <p>🔴 Conflicts: {stats.conflict}</p>
                </div>
                <hr />
                {Object.entries(layers).map(([key, l]) => (
                    <div key={key} className="legend-row">
                        <input type="checkbox" checked={l.visible} onChange={() => setLayers(prev => ({ ...prev, [key]: { ...prev[key], visible: !l.visible } }))} />
                        <span className="swatch" style={{ background: l.color }}></span>
                        <span>{l.label}</span>
                    </div>
                ))}
                {buffer && <button className="clear-btn" onClick={() => setBuffer(null)}>Clear Analysis</button>}
            </div>

            <MapContainer center={[47.6062, -122.3321]} zoom={15} style={{ flex: 1 }}>
                <LayersControl position="topright">
                    <BaseLayer checked name="Streets"><TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" /></BaseLayer>
                    <BaseLayer name="Satellite"><TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" /></BaseLayer>
                </LayersControl>

                <MapEvents onMove={fetchAll} />

                {/* Admin Parcels + Attributes Popup */}
                {layers.parcels.visible && layers.parcels.data && (
                    <GeoJSON 
                        key={`p-${JSON.stringify(layers.parcels.data.features?.length)}`} 
                        data={layers.parcels.data} 
                        style={{ color: '#3498db', weight: 3, fillOpacity: 0.1 }}
                        onEachFeature={(f, l) => l.bindPopup(`<strong>Admin Parcel</strong><br>Name: ${f.properties.name}<br>City: ${f.properties.city}`)}
                    />
                )}

                {/* Zoning Map + Attributes Popup */}
                {layers.zoning.visible && layers.zoning.data && (
                    <GeoJSON 
                        key={`z-${JSON.stringify(layers.zoning.data.features?.length)}`} 
                        data={layers.zoning.data} 
                        style={{ color: '#f1c40f', weight: 1, fillOpacity: 0.3 }}
                        onEachFeature={(f, l) => l.bindPopup(`<strong>Zoning Area</strong><br>Code: ${f.properties.code}<br>Category: ${f.properties.category}`)}
                    />
                )}

                {/* Building Footprints + Buffer Logic */}
                {layers.buildings.visible && layers.buildings.data && (
                    <GeoJSON 
                        key={`b-${JSON.stringify(layers.buildings.data.features?.length)}`} 
                        data={layers.buildings.data} 
                        style={(f) => ({ fillColor: f.properties.status === 'Conflict' ? '#e74c3c' : '#2ecc71', color: 'white', weight: 1, fillOpacity: 0.8 })}
                        onEachFeature={(f, l) => {
                            l.bindPopup(`<strong>Building</strong><br>PIN: ${f.properties.pin}<br>Status: ${f.properties.status}`);
                            l.on('click', (e) => { L.DomEvent.stopPropagation(e); handleBuildingClick(f); });
                        }}
                    />
                )}

                {/* Buffer Layer (Key ensures it moves on click) */}
                {buffer && (
                    <GeoJSON 
                        key={`buf-${JSON.stringify(buffer.geometry.coordinates)}`} 
                        data={buffer} 
                        style={{ color: 'cyan', weight: 2, dashArray: '5, 5', fillOpacity: 0.3 }} 
                    />
                )}
            </MapContainer>
        </div>
    );
}

export default App;