"use client";

// =============================================================================
// TrackingMap - Leaflet Map Component for Delivery Tracking
// =============================================================================
// Displays an interactive map with delivery markers.
// When a delivery is selected, the map flies to that location.
// =============================================================================

import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { MockDelivery } from "@/app/(main)/ferramentas/ativos/tracking/page";

// =============================================================================
// Fix Leaflet default marker icons (webpack issue)
// =============================================================================

// Custom marker icon
const createCustomIcon = (isSelected: boolean) => {
  return L.divIcon({
    className: "custom-marker",
    html: `
      <div style="
        width: ${isSelected ? "40px" : "32px"};
        height: ${isSelected ? "40px" : "32px"};
        background: ${isSelected ? "#3b82f6" : "#6366f1"};
        border: 3px solid white;
        border-radius: 50% 50% 50% 0;
        transform: rotate(-45deg);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        transition: all 0.3s ease;
      ">
        <div style="
          width: ${isSelected ? "16px" : "12px"};
          height: ${isSelected ? "16px" : "12px"};
          background: white;
          border-radius: 50%;
          transform: rotate(45deg);
        "></div>
      </div>
    `,
    iconSize: [isSelected ? 40 : 32, isSelected ? 40 : 32],
    iconAnchor: [isSelected ? 20 : 16, isSelected ? 40 : 32],
    popupAnchor: [0, isSelected ? -40 : -32],
  });
};

// =============================================================================
// Map Controller - Handles flying to selected delivery
// =============================================================================

interface MapControllerProps {
  selectedDelivery: MockDelivery | null;
}

function MapController({ selectedDelivery }: MapControllerProps) {
  const map = useMap();

  useEffect(() => {
    if (selectedDelivery) {
      map.flyTo([selectedDelivery.lat, selectedDelivery.lng], 12, {
        duration: 1.5,
      });
    }
  }, [selectedDelivery, map]);

  return null;
}

// =============================================================================
// TrackingMap Component
// =============================================================================

interface TrackingMapProps {
  deliveries: MockDelivery[];
  selectedDelivery: MockDelivery | null;
  onDeliverySelect: (delivery: MockDelivery) => void;
}

export default function TrackingMap({
  deliveries,
  selectedDelivery,
  onDeliverySelect,
}: TrackingMapProps) {
  const mapRef = useRef<L.Map | null>(null);

  // Brazil center coordinates
  const defaultCenter: [number, number] = [-15.7801, -47.9292];
  const defaultZoom = 4;

  return (
    <MapContainer
      center={defaultCenter}
      zoom={defaultZoom}
      className="h-full w-full"
      ref={mapRef}
      style={{ background: "#1a1d28" }}
    >
      {/* Dark themed tile layer */}
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />

      {/* Map controller for flying to selected delivery */}
      <MapController selectedDelivery={selectedDelivery} />

      {/* Delivery markers */}
      {deliveries.map((delivery) => {
        const isSelected = selectedDelivery?.id === delivery.id;
        return (
          <Marker
            key={delivery.id}
            position={[delivery.lat, delivery.lng]}
            icon={createCustomIcon(isSelected)}
            eventHandlers={{
              click: () => onDeliverySelect(delivery),
            }}
          >
            <Popup>
              <div className="min-w-[200px]">
                <div className="font-semibold text-gray-900 mb-1">
                  {delivery.codigo}
                </div>
                <div className="text-sm text-gray-700 mb-2">
                  {delivery.cliente}
                </div>
                <div className="text-xs text-gray-500 space-y-1">
                  <div className="flex items-center gap-1">
                    <span className="font-medium">Destino:</span>
                    <span>{delivery.destino}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="font-medium">Endereco:</span>
                    <span>{delivery.endereco}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="font-medium">Previsao:</span>
                    <span>{new Date(delivery.previsao).toLocaleDateString("pt-BR")}</span>
                  </div>
                </div>
                <div className="mt-2 pt-2 border-t border-gray-200">
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                    Em Transito
                  </span>
                </div>
              </div>
            </Popup>
          </Marker>
        );
      })}
    </MapContainer>
  );
}
