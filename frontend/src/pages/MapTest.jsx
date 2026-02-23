import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet';

const CENTER = [40.7128, -74.006];

export default function MapTest() {
  return (
    <div className="mx-auto max-w-[1600px] p-4 md:p-8">
      <h1 className="mb-4 text-2xl font-bold text-slate-900">Map Test</h1>
      <div className="h-[70vh] overflow-hidden rounded-xl border border-slate-200">
        <MapContainer center={CENTER} zoom={10} scrollWheelZoom className="h-full w-full">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <Marker position={CENTER}>
            <Popup>Map rendering check</Popup>
          </Marker>
        </MapContainer>
      </div>
    </div>
  );
}
